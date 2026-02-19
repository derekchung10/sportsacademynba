"""
SMS Batch Extraction Service

Each individual SMS gets its own Interaction record immediately (so it
appears as a chat bubble in the UI).  The *LLM extraction* is what gets
batched: we defer it until the thread goes quiet, then run a single LLM
call on the combined transcript and apply the results to the last
interaction in the batch.

- scan_for_urgency()   — fast keyword check; triggers immediate flush
- flush_sms_thread()   — run LLM once on combined thread, apply to last interaction
- check_sms_flush()    — django-q task; evaluates the three flush criteria
- flush_stale_threads() — periodic sweep; safety net for missed tasks
"""
import logging
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

from django.db import transaction
from django.db.models import Count, Min, Max

from app.models.interaction import Interaction
from app.models.sms_buffer import SMSBuffer

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────

QUIET_PERIOD = timedelta(minutes=5)
MAX_ACCUMULATION = timedelta(minutes=15)
MAX_BUFFERED_MESSAGES = 6

# ─── Urgent keyword patterns ─────────────────────────────────────────────────

_URGENT_PATTERNS = [
    re.compile(r"\b(stop|unsubscribe|opt.?out|remove me|do not (contact|text|call))\b", re.I),
    re.compile(r"\b(sign.?up|enroll|register|i('?m| am) in|let('?s| us) do it|ready to start)\b", re.I),
    re.compile(r"\b(schedule|book|appointment|visit|come (by|in|over)|tour)\b", re.I),
    re.compile(r"\b(emergency|urgent|asap|right now|immediately)\b", re.I),
]


def scan_for_urgency(body: str) -> bool:
    """Return True if the message body contains an urgent signal."""
    return any(p.search(body) for p in _URGENT_PATTERNS)


# ─── Flush logic ──────────────────────────────────────────────────────────────

def flush_sms_thread(lead_id: UUID) -> dict | None:
    """
    Collect all unflushed SMSBuffer rows for a lead.  Each row already
    has its own Interaction record (created on arrival).  We build a
    combined transcript, run the processing pipeline ONCE on the last
    interaction, and mark the batch as flushed.

    Returns the pipeline result dict, or None if there was nothing to flush.
    """
    from app.services.interaction_processor import process_interaction

    with transaction.atomic():
        buffers = (
            SMSBuffer.objects
            .select_for_update()
            .filter(lead_id=lead_id, flushed=False)
            .select_related("interaction")
            .order_by("received_at")
        )
        buf_list = list(buffers)
        if not buf_list:
            return None

        combined_transcript = _build_thread_transcript(buf_list)

        anchor = buf_list[-1].interaction
        if anchor is None:
            logger.error("SMSBuffer %s has no linked Interaction", buf_list[-1].id)
            return None

        buffers.update(flushed=True)

    logger.info(
        "Flushed %d SMS messages for lead %s → processing interaction %s",
        len(buf_list), lead_id, anchor.id,
    )

    result = process_interaction(anchor, transcript_override=combined_transcript)
    return result


def _build_thread_transcript(buffers: list[SMSBuffer]) -> str:
    """Build a combined transcript from buffered messages for the LLM."""
    lines = []
    for buf in buffers:
        ts = buf.received_at.strftime("%Y-%m-%d %H:%M:%S")
        label = "Customer" if buf.direction == "inbound" else "Academy"
        lines.append(f"[{ts} | {label}] {buf.body}")
    return "\n".join(lines)


# ─── django-q task: per-lead flush check ──────────────────────────────────────

def check_sms_flush(lead_id: str) -> str:
    """
    Scheduled by the API when a non-urgent SMS arrives.  Evaluates whether
    the thread should be flushed now or rescheduled.

    Accepts lead_id as a string (django-q serializes task args as JSON).
    Returns a short status string for the task log.
    """
    from django_q.tasks import async_task

    lead_uuid = UUID(lead_id)
    now = datetime.now(timezone.utc)

    pending = (
        SMSBuffer.objects
        .filter(lead_id=lead_uuid, flushed=False)
        .aggregate(
            count=Count("id"),
            oldest=Min("received_at"),
            newest=Max("received_at"),
        )
    )

    count = pending["count"] or 0
    if count == 0:
        return "no_pending_messages"

    oldest: datetime = pending["oldest"]
    newest: datetime = pending["newest"]

    should_flush = (
        count >= MAX_BUFFERED_MESSAGES
        or (now - oldest) >= MAX_ACCUMULATION
        or (now - newest) >= QUIET_PERIOD
    )

    if should_flush:
        flush_sms_thread(lead_uuid)
        return f"flushed ({count} messages)"

    async_task(
        "app.services.sms_batcher.check_sms_flush",
        lead_id,
        task_name=f"sms_flush_check_{lead_id}",
        q_options={"timeout": 60},
    )
    return f"rescheduled (count={count}, age={now - oldest})"


# ─── Periodic sweep: safety net ───────────────────────────────────────────────

def flush_stale_threads() -> str:
    """
    Runs every minute via django-q Schedule.  Finds any lead with buffered
    messages older than MAX_ACCUMULATION and flushes them.

    This catches edge cases where the per-lead task was lost (worker restart,
    ORM broker hiccup, etc.).
    """
    cutoff = datetime.now(timezone.utc) - MAX_ACCUMULATION

    stale_leads = (
        SMSBuffer.objects
        .filter(flushed=False, received_at__lte=cutoff)
        .values_list("lead_id", flat=True)
        .distinct()
    )

    flushed_count = 0
    for lead_id in stale_leads:
        try:
            flush_sms_thread(lead_id)
            flushed_count += 1
        except Exception:
            logger.exception("Failed to flush stale SMS thread for lead %s", lead_id)

    return f"sweep complete: {flushed_count} threads flushed"

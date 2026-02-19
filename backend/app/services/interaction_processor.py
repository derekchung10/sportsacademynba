"""
Interaction Processing Pipeline

This is the core orchestrator. When an interaction is submitted:
1. Log an event
2. Run LLM extraction (summary, facts, intent, sentiment)
3. Persist context artifacts
4. Update lead state (status, counters)
5. Q-table update: reward the previous action based on the state transition
6. Run RL-based NBA engine to produce next best action (with full action brief)
7. Log the NBA decision event

Design choice: Synchronous pipeline (not event-driven) for simplicity.
In production, steps 2+ could be async (background job/queue) to avoid
blocking the API response. For this demo, sync is fine and more inspectable.
"""
import logging
from datetime import datetime, timezone

from django.db import transaction
from django.db.models import F

from app.models.lead import Lead
from app.models.interaction import Interaction
from app.models.event import Event
from app.models.nba_decision import NBADecision
from app.services.llm_service import extract_from_interaction
from app.services.context_service import enrich_from_extraction
from app.services.nba_engine import compute_nba, persist_nba_decision
from app.services.rl_engine import encode_state, update_q_table
from app.utils import build_child_info

logger = logging.getLogger(__name__)


def process_interaction(interaction: Interaction, transcript_override: str = None) -> dict:
    """
    Full processing pipeline for a completed interaction.
    Returns a summary of what was produced.

    transcript_override: if provided, the LLM sees this text instead of
    interaction.transcript. Used by the SMS batcher so the LLM gets the
    full thread context while results are stored on this single interaction.
    """
    lead = Lead.objects.filter(id=interaction.lead_id).first()
    if not lead:
        raise ValueError(f"Lead {interaction.lead_id} not found")

    results = {
        "interaction_id": str(interaction.id),
        "lead_id": str(lead.id),
        "steps": [],
    }

    llm_transcript = transcript_override or interaction.transcript

    # ─── Step 1: Log interaction event (outside main txn — append-only) ──
    Event.objects.create(
        lead_id=lead.id,
        event_type="interaction_completed",
        source="system",
        source_id=str(interaction.id),
        payload={
            "channel": interaction.channel,
            "direction": interaction.direction,
            "status": interaction.status,
            "duration_seconds": interaction.duration_seconds,
        },
        description=(
            f"{interaction.channel.title()} {interaction.direction} — {interaction.status}"
            + (f" ({interaction.duration_seconds}s)" if interaction.duration_seconds else "")
        ),
    )
    results["steps"].append("event_logged")

    # ─── Step 2: LLM extraction (outside txn — may be a slow HTTP call) ──
    extraction = extract_from_interaction(
        transcript=llm_transcript,
        lead_name=f"{lead.first_name} {lead.last_name}",
        child_info=build_child_info(lead),
        sport=lead.sport or "",
        academy_name=lead.academy_name or "",
        campaign_goal=lead.campaign_goal or "",
        channel=interaction.channel,
        direction=interaction.direction,
        status=interaction.status,
    )

    # Update interaction with LLM results
    interaction.summary = extraction.summary
    interaction.extracted_facts = extraction.facts
    interaction.detected_intent = extraction.intent
    interaction.sentiment = extraction.sentiment
    interaction.open_questions = extraction.open_questions
    interaction.processed = True
    interaction.processed_at = datetime.now(timezone.utc)
    interaction.save()
    results["steps"].append("llm_extraction")

    # ─── Steps 3-6: DB mutations in a single transaction ─────────────────
    with transaction.atomic():
        # Re-fetch lead with row lock to prevent lost updates
        lead = Lead.objects.select_for_update().get(id=lead.id)

        # Step 3: Persist context artifacts
        artifacts = enrich_from_extraction(lead.id, interaction.id, extraction)
        results["steps"].append(f"context_artifacts_created ({len(artifacts)})")

        Event.objects.create(
            lead_id=lead.id,
            event_type="context_enriched",
            source="system",
            source_id=str(interaction.id),
            payload={
                "summary": extraction.summary,
                "intent": extraction.intent,
                "sentiment": extraction.sentiment,
                "fact_count": len(extraction.facts),
            },
            description=f"Context enriched: intent={extraction.intent}, sentiment={extraction.sentiment}",
        )

        # Step 4: Update lead state with atomic counter increments
        old_status = lead.status

        counter_updates = {
            "total_interactions": F("total_interactions") + 1,
        }
        if interaction.channel == "voice":
            counter_updates["total_voice_attempts"] = F("total_voice_attempts") + 1
        elif interaction.channel == "sms":
            counter_updates["total_sms_attempts"] = F("total_sms_attempts") + 1
        elif interaction.channel == "email":
            counter_updates["total_email_attempts"] = F("total_email_attempts") + 1

        Lead.objects.filter(id=lead.id).update(**counter_updates)

        # Derive new status from intent
        new_status = _derive_lead_status(lead.status, extraction.intent, interaction.status)
        if new_status != old_status:
            lead.status = new_status
            lead.save(update_fields=["status", "updated_at"])
            Event.objects.create(
                lead_id=lead.id,
                event_type="status_changed",
                source="system",
                source_id=str(interaction.id),
                payload={"old_status": old_status, "new_status": new_status},
                description=f"Status changed: {old_status} -> {new_status}",
            )
            results["steps"].append(f"status_updated ({old_status} -> {new_status})")

        # Refresh to get updated counters for downstream use
        lead.refresh_from_db()

        # Step 5: Q-table update (reward previous action)
        _update_q_table_from_transition(lead, old_status, new_status, results)

        # Step 6: Compute NBA via RL engine
        action_brief, policy_inputs = compute_nba(lead, interaction)

        decision = persist_nba_decision(lead, action_brief, str(interaction.id), policy_inputs)
        results["steps"].append(
            f"nba_produced ({action_brief.semantic_action}/{action_brief.channel})"
        )

        Event.objects.create(
            lead_id=lead.id,
            event_type="nba_produced",
            source="system",
            source_id=str(decision.id),
            payload={
                "action": action_brief.semantic_action,
                "channel": action_brief.channel,
                "priority": action_brief.priority,
                "rl_state": action_brief.state,
                "rl_q_value": action_brief.q_value,
                "scheduled_for": action_brief.scheduled_for.isoformat() if action_brief.scheduled_for else None,
            },
            description=(
                f"NBA: {action_brief.semantic_action} via {action_brief.channel or 'N/A'} "
                f"(priority={action_brief.priority}, state={action_brief.state}, q={action_brief.q_value:.3f})"
            ),
        )

    results["steps"].append("committed")

    logger.info(
        f"Processed interaction {interaction.id} for lead {lead.id}: "
        f"{' -> '.join(results['steps'])}"
    )
    return results


def _derive_lead_status(current_status: str, intent: str, interaction_status: str) -> str:
    """
    Derive the new lead status from the detected intent.

    Full lifecycle:
      Acquisition: new → contacted → interested → trial → enrolled
      Retention:   enrolled → active → at_risk → inactive
      Terminal:    declined, unresponsive

    Retention statuses (active, at_risk, inactive) are only reachable from
    enrolled or other retention statuses — the acquisition funnel can't skip
    directly to "active."
    """
    if interaction_status == "opted_out":
        return "declined"

    # ─── Retention path (already enrolled / active / at_risk / inactive) ───
    retention_statuses = {"enrolled", "active", "at_risk", "inactive"}
    if current_status in retention_statuses:
        return _derive_retention_status(current_status, intent, interaction_status)

    # ─── Acquisition path (new → contacted → interested → trial → enrolled) ─
    intent_to_status = {
        "interested": "interested",
        "scheduling": "trial",
        "attending": "trial",
        "considering": "interested",
        "requesting_info": "contacted",
        "objecting": current_status if current_status != "new" else "contacted",
        "declining": "declined",
        "no_response": current_status if current_status != "new" else "contacted",
        "unclear": current_status if current_status != "new" else "contacted",
    }

    proposed = intent_to_status.get(intent, current_status)

    # Don't regress in the acquisition funnel
    acquisition_order = ["new", "contacted", "interested", "trial", "enrolled"]
    terminal = ["declined", "unresponsive"]

    if proposed in terminal:
        return proposed

    current_idx = acquisition_order.index(current_status) if current_status in acquisition_order else 0
    proposed_idx = acquisition_order.index(proposed) if proposed in acquisition_order else 0

    return proposed if proposed_idx >= current_idx else current_status


def _derive_retention_status(current_status: str, intent: str, interaction_status: str) -> str:
    """
    Derive status changes for families already in the retention phase.
    enrolled → active (confirmed attending)
    active → at_risk (signals of dropping off)
    at_risk → active (re-engaged) or inactive (gone quiet)
    inactive → active (came back!) or at_risk (showed some interest)
    """
    if intent == "declining":
        return "inactive"

    if intent in ("interested", "scheduling", "attending"):
        # Positive signal — they're engaged / coming to class
        return "active"

    if intent in ("considering", "requesting_info"):
        # Some engagement but not fully back
        if current_status == "inactive":
            return "at_risk"  # Coming back from inactive — not fully active yet
        return current_status

    if intent == "objecting":
        # Pushing back — could be at risk
        if current_status == "active":
            return "at_risk"
        return current_status

    if intent in ("no_response", "unclear"):
        if current_status == "active":
            return current_status  # One missed contact doesn't make them at_risk
        return current_status

    return current_status


# ─── RL Q-Table Update ───────────────────────────────────────────────────────

def _update_q_table_from_transition(lead, old_status, new_status, results):
    """
    After a status change, reward or penalize the previous NBA decision's action.
    This is the learning step of the RL engine.
    """
    previous_decision = (
        NBADecision.objects
        .filter(lead_id=lead.id, is_current=True)
        .first()
    )
    if not previous_decision or not previous_decision.rl_state:
        return

    state_before = previous_decision.rl_state
    action_taken = previous_decision.action

    # Build state_after: replace the status part of the state string.
    # The context bucket may have changed too, but we approximate with the same
    # bucket here — the full recomputation happens in compute_nba.
    state_parts = state_before.split(":")
    context_bucket = state_parts[1] if len(state_parts) > 1 else "neutral"
    state_after = f"{new_status}:{context_bucket}"

    transition = update_q_table(
        lead_id=lead.id,
        nba_decision_id=previous_decision.id,
        state_before=state_before,
        action_taken=action_taken,
        state_after=state_after,
        status_before=old_status,
        status_after=new_status,
    )

    if transition:
        results["steps"].append(
            f"q_update (r={transition.reward:+.2f}, "
            f"Q={transition.q_value_before:.3f}->{transition.q_value_after:.3f})"
        )

"""
Next Best Action (NBA) Decisioning Engine

Design: Deterministic, rule-based policy engine.
- Same inputs → same outputs (testable, auditable)
- LLM provides context (summaries, intent, enriched dimensions); rules provide decisions
- Rules are ordered by priority; first match wins
- Policy inputs are snapshotted with each decision for reproducibility

Full lifecycle statuses:
  Acquisition: new → contacted → interested → trial → enrolled
  Retention:   enrolled → active → at_risk → inactive
  Terminal:    declined, unresponsive

Rule categories:
1. Terminal states (declined, opted out)
2. Immediate responses (inbound interest, scheduling requests)
3. Retention rules (at_risk re-engagement, inactive win-back, attendance check-in)
4. Context-aware rules (financial concerns, objections, family opportunities)
5. Follow-up rules (after no answer, after voicemail)
6. Channel escalation (tried voice N times → switch to SMS)
7. Cool-down rules (don't over-contact)
"""
import json
import logging
from datetime import datetime, timedelta, timezone

from django.conf import settings as django_settings

from app.models.lead import Lead
from app.models.interaction import Interaction
from app.models.context_artifact import ContextArtifact
from app.models.nba_decision import NBADecision
from app.models.scheduled_action import ScheduledAction

logger = logging.getLogger(__name__)


class PolicyInputs:
    """Snapshot of all data the NBA engine evaluates, including enriched context."""
    def __init__(
        self,
        lead_status: str,
        total_interactions: int,
        total_voice_attempts: int,
        total_sms_attempts: int,
        total_email_attempts: int,
        last_interaction_channel: str | None,
        last_interaction_status: str | None,
        last_interaction_direction: str | None,
        last_detected_intent: str | None,
        last_sentiment: str | None,
        hours_since_last_interaction: float | None,
        campaign_goal: str | None,
        preferred_channel: str | None,
        has_phone: bool,
        has_email: bool,
        # Enriched context dimensions (Option D)
        financial_concern_level: str = "none",
        has_unaddressed_objections: bool = False,
        objection_topics: list[str] | None = None,
        has_scheduling_constraints: bool = False,
        has_siblings: bool = False,
        has_pending_decision_makers: bool = False,
    ):
        self.lead_status = lead_status
        self.total_interactions = total_interactions
        self.total_voice_attempts = total_voice_attempts
        self.total_sms_attempts = total_sms_attempts
        self.total_email_attempts = total_email_attempts
        self.last_interaction_channel = last_interaction_channel
        self.last_interaction_status = last_interaction_status
        self.last_interaction_direction = last_interaction_direction
        self.last_detected_intent = last_detected_intent
        self.last_sentiment = last_sentiment
        self.hours_since_last_interaction = hours_since_last_interaction
        self.campaign_goal = campaign_goal
        self.preferred_channel = preferred_channel
        self.has_phone = has_phone
        self.has_email = has_email
        # Enriched context
        self.financial_concern_level = financial_concern_level
        self.has_unaddressed_objections = has_unaddressed_objections
        self.objection_topics = objection_topics or []
        self.has_scheduling_constraints = has_scheduling_constraints
        self.has_siblings = has_siblings
        self.has_pending_decision_makers = has_pending_decision_makers

    def to_dict(self) -> dict:
        return self.__dict__


class NBAResult:
    """The output of the NBA engine."""
    def __init__(self, action: str, channel: str | None, priority: str,
                 reasoning: str, rule_name: str, scheduled_for: datetime | None = None):
        self.action = action
        self.channel = channel
        self.priority = priority
        self.reasoning = reasoning
        self.rule_name = rule_name
        self.scheduled_for = scheduled_for


def _now() -> datetime:
    """Central timestamp helper for testability."""
    return datetime.now(timezone.utc)


def _load_enriched_context(lead_id) -> dict:
    """
    Load accumulated enriched context from artifacts for a lead.
    Returns a dict with financial, scheduling, family, and objection signals.
    """
    CONCERN_LEVEL_ORDER = {"none": 0, "low": 1, "moderate": 2, "high": 3}

    result = {
        "financial_concern_level": "none",
        "objection_topics": [],
        "has_unaddressed_objections": False,
        "has_scheduling_constraints": False,
        "has_siblings": False,
        "has_pending_decision_makers": False,
    }

    current_artifacts = ContextArtifact.objects.filter(lead_id=lead_id, is_current=True)
    for artifact in current_artifacts:
        try:
            if artifact.artifact_type == "financial_signals":
                data = json.loads(artifact.content)
                level = data.get("concern_level", "none")
                if CONCERN_LEVEL_ORDER.get(level, 0) > CONCERN_LEVEL_ORDER.get(result["financial_concern_level"], 0):
                    result["financial_concern_level"] = level

            elif artifact.artifact_type == "objections":
                data = json.loads(artifact.content)
                for obj in data:
                    topic = obj.get("topic", "unknown")
                    if topic not in result["objection_topics"]:
                        result["objection_topics"].append(topic)
                if data:
                    result["has_unaddressed_objections"] = True

            elif artifact.artifact_type == "scheduling_constraints":
                data = json.loads(artifact.content)
                if data.get("constraints") or data.get("preferred_times"):
                    result["has_scheduling_constraints"] = True

            elif artifact.artifact_type == "family_context":
                data = json.loads(artifact.content)
                if data.get("siblings"):
                    result["has_siblings"] = True
                if data.get("decision_makers"):
                    result["has_pending_decision_makers"] = True

        except (json.JSONDecodeError, TypeError):
            continue

    return result


def _build_policy_inputs(lead: Lead, last_interaction: Interaction | None) -> PolicyInputs:
    """Build policy inputs from lead state, last interaction, and enriched context."""
    hours_since = None
    if last_interaction and last_interaction.created_at:
        delta = _now() - last_interaction.created_at
        hours_since = delta.total_seconds() / 3600

    # Load enriched context dimensions from stored artifacts
    enriched = _load_enriched_context(lead.id)

    return PolicyInputs(
        lead_status=lead.status,
        total_interactions=lead.total_interactions,
        total_voice_attempts=lead.total_voice_attempts,
        total_sms_attempts=lead.total_sms_attempts,
        total_email_attempts=lead.total_email_attempts,
        last_interaction_channel=last_interaction.channel if last_interaction else None,
        last_interaction_status=last_interaction.status if last_interaction else None,
        last_interaction_direction=last_interaction.direction if last_interaction else None,
        last_detected_intent=last_interaction.detected_intent if last_interaction else None,
        last_sentiment=last_interaction.sentiment if last_interaction else None,
        hours_since_last_interaction=hours_since,
        campaign_goal=lead.campaign_goal,
        preferred_channel=lead.preferred_channel,
        has_phone=bool(lead.phone),
        has_email=bool(lead.email),
        # Enriched context
        financial_concern_level=enriched["financial_concern_level"],
        has_unaddressed_objections=enriched["has_unaddressed_objections"],
        objection_topics=enriched["objection_topics"],
        has_scheduling_constraints=enriched["has_scheduling_constraints"],
        has_siblings=enriched["has_siblings"],
        has_pending_decision_makers=enriched["has_pending_decision_makers"],
    )


def compute_nba(lead: Lead, latest_interaction: Interaction | None = None) -> tuple[NBAResult, PolicyInputs]:
    """
    Evaluate rules against current lead state and produce the next best action.
    Returns (NBAResult, PolicyInputs) so callers can persist both without rebuilding.
    """
    last_interaction = latest_interaction or (
        Interaction.objects
        .filter(lead_id=lead.id)
        .order_by("-created_at")
        .first()
    )

    inputs = _build_policy_inputs(lead, last_interaction)

    # Evaluate rules in priority order
    result = _evaluate_rules(inputs)
    return result, inputs


def _evaluate_rules(inputs: PolicyInputs) -> NBAResult:
    """
    Rule engine: evaluate rules in priority order, first match wins.
    Each rule returns an NBAResult or None (no match).
    """
    rules = [
        # Terminal / compliance
        _rule_terminal_state,
        _rule_opted_out,
        # Immediate responses
        _rule_inbound_interest,
        _rule_scheduling_request,
        _rule_requesting_info,
        # Retention rules (for enrolled/active/at_risk/inactive families)
        _rule_at_risk_reengagement,
        _rule_inactive_winback,
        _rule_active_checkin,
        _rule_enrolled_welcome,
        # Context-aware rules (Option D)
        _rule_financial_concern,
        _rule_unaddressed_objection,
        _rule_pending_decision_maker,
        _rule_sibling_opportunity,
        # Engagement-based follow-ups
        _rule_positive_engagement,
        _rule_considering,
        _rule_objecting,
        # Channel / retry mechanics
        _rule_channel_escalation,
        _rule_voicemail_follow_up,
        _rule_no_answer_retry,
        _rule_cool_down,
        # Initial / default
        _rule_new_lead,
        _rule_default,
    ]

    for rule_fn in rules:
        result = rule_fn(inputs)
        if result is not None:
            return result

    # Should never reach here given _rule_default, but safety net
    return NBAResult(
        action="no_action",
        channel=None,
        priority="low",
        reasoning="No applicable rule matched. Manual review recommended.",
        rule_name="fallback",
    )


# ─── Terminal / Compliance Rules ─────────────────────────────────────────────

def _rule_terminal_state(inputs: PolicyInputs) -> NBAResult | None:
    """Leads that have reached a terminal state need no further action."""
    if inputs.lead_status == "declined":
        return NBAResult(
            action="no_action",
            channel=None,
            priority="low",
            reasoning="Family has declined. Respecting their decision — no further outreach.",
            rule_name="terminal_state",
        )
    return None


def _rule_opted_out(inputs: PolicyInputs) -> NBAResult | None:
    """Respect opt-out."""
    if inputs.last_interaction_status == "opted_out":
        return NBAResult(
            action="no_action",
            channel=None,
            priority="low",
            reasoning="Lead opted out of communications. Marked as declined.",
            rule_name="opted_out",
        )
    return None


# ─── Immediate Response Rules ────────────────────────────────────────────────

def _rule_inbound_interest(inputs: PolicyInputs) -> NBAResult | None:
    """Inbound call/message with positive intent → high priority call back."""
    if (inputs.last_interaction_direction == "inbound"
            and inputs.last_detected_intent in ("interested", "scheduling")):
        channel = inputs.preferred_channel or "voice"
        return NBAResult(
            action="call",
            channel=channel,
            priority="urgent",
            reasoning=(
                f"Lead reached out (inbound) with '{inputs.last_detected_intent}' intent. "
                f"High-priority follow-up via {channel} to capitalize on interest."
            ),
            rule_name="inbound_interest",
            scheduled_for=_now() + timedelta(hours=1),
        )
    return None


def _rule_scheduling_request(inputs: PolicyInputs) -> NBAResult | None:
    """Lead wants to schedule → immediate action."""
    if inputs.last_detected_intent == "scheduling":
        return NBAResult(
            action="schedule_visit",
            channel="voice",
            priority="urgent",
            reasoning="Lead expressed intent to schedule. Call immediately to lock in the visit.",
            rule_name="scheduling_request",
            scheduled_for=_now() + timedelta(minutes=30),
        )
    return None


def _rule_requesting_info(inputs: PolicyInputs) -> NBAResult | None:
    """Lead asked for information → send via SMS/email, then follow up."""
    if inputs.last_detected_intent == "requesting_info":
        channel = "sms" if inputs.has_phone else ("email" if inputs.has_email else "voice")
        return NBAResult(
            action="sms",
            channel=channel,
            priority="high",
            reasoning=(
                "Lead requested more information. Send details via "
                f"{channel} (quick, non-intrusive), then follow up with a call in 24h."
            ),
            rule_name="requesting_info",
            scheduled_for=_now() + timedelta(hours=2),
        )
    return None


# ─── Retention Rules ─────────────────────────────────────────────────────────

def _rule_at_risk_reengagement(inputs: PolicyInputs) -> NBAResult | None:
    """Family was active but attendance is dropping → proactive check-in."""
    if inputs.lead_status == "at_risk":
        channel = inputs.preferred_channel or "voice"
        return NBAResult(
            action="call" if channel == "voice" else channel,
            channel=channel,
            priority="high",
            reasoning=(
                "This family was attending regularly but seems to be dropping off. "
                "Call to check in — ask if there are scheduling issues, if the child "
                "is still enjoying the program, or if anything changed. A personal touch "
                "now can prevent them from going inactive."
            ),
            rule_name="at_risk_reengagement",
            scheduled_for=_now() + timedelta(hours=4),
        )
    return None


def _rule_inactive_winback(inputs: PolicyInputs) -> NBAResult | None:
    """Family stopped attending entirely → win-back outreach."""
    if inputs.lead_status == "inactive":
        # Start with SMS — less intrusive for someone who's been away
        channel = "sms" if inputs.has_phone else ("email" if inputs.has_email else "voice")
        hours_gap = inputs.hours_since_last_interaction or 0
        if hours_gap > 168:  # Over a week since last contact
            return NBAResult(
                action="sms",
                channel=channel,
                priority="normal",
                reasoning=(
                    "Family hasn't been attending and it's been over a week since last contact. "
                    "Send a friendly, low-pressure message checking in. Mention what's new at the "
                    "academy or upcoming events that might spark interest again."
                ),
                rule_name="inactive_winback",
                scheduled_for=_now() + timedelta(hours=12),
            )
        return NBAResult(
            action="wait",
            channel=None,
            priority="low",
            reasoning=(
                "Family is inactive but was contacted recently. Give them space before "
                "following up again."
            ),
            rule_name="inactive_cooldown",
            scheduled_for=_now() + timedelta(hours=72),
        )
    return None


def _rule_active_checkin(inputs: PolicyInputs) -> NBAResult | None:
    """Actively attending family → occasional positive touchpoint."""
    if inputs.lead_status == "active":
        hours_gap = inputs.hours_since_last_interaction or 999
        if hours_gap > 168:  # Haven't talked in over a week
            return NBAResult(
                action="sms",
                channel="sms",
                priority="low",
                reasoning=(
                    "Family is actively attending — great! Send a positive check-in: "
                    "share their child's progress, mention upcoming events, or ask "
                    "for a referral. Keep the relationship warm."
                ),
                rule_name="active_checkin",
                scheduled_for=_now() + timedelta(hours=48),
            )
        return NBAResult(
            action="no_action",
            channel=None,
            priority="low",
            reasoning=(
                "Family is actively attending and we've been in touch recently. "
                "No action needed — they're in a healthy state."
            ),
            rule_name="active_healthy",
        )
    return None


def _rule_enrolled_welcome(inputs: PolicyInputs) -> NBAResult | None:
    """Just enrolled → welcome message and class reminder."""
    if inputs.lead_status == "enrolled":
        channel = inputs.preferred_channel or "sms"
        return NBAResult(
            action="sms",
            channel=channel,
            priority="high",
            reasoning=(
                "Family just enrolled! Send a warm welcome message with class schedule, "
                "what to bring, and what to expect on their first day. Getting them to "
                "their first class is the most important step to long-term retention."
            ),
            rule_name="enrolled_welcome",
            scheduled_for=_now() + timedelta(hours=2),
        )
    return None


# ─── Context-Aware Rules (Option D) ─────────────────────────────────────────

def _rule_financial_concern(inputs: PolicyInputs) -> NBAResult | None:
    """
    Lead has expressed financial concerns → pivot to scholarship/payment info.
    Don't hard-sell; address the concern directly with helpful information.
    """
    if inputs.financial_concern_level in ("moderate", "high") and inputs.last_detected_intent not in ("declining", "objecting"):
        channel = "sms" if inputs.has_phone else ("email" if inputs.has_email else "voice")
        severity = inputs.financial_concern_level
        return NBAResult(
            action="sms",
            channel=channel,
            priority="high" if severity == "high" else "normal",
            reasoning=(
                f"Lead has {severity} financial concerns. Send scholarship/financial aid "
                f"information via {channel} before next call. Addressing cost concerns "
                "proactively builds trust and removes a key barrier to enrollment."
            ),
            rule_name="financial_concern_outreach",
            scheduled_for=_now() + timedelta(hours=4),
        )
    return None


def _rule_unaddressed_objection(inputs: PolicyInputs) -> NBAResult | None:
    """
    Lead raised specific objections (distance, safety, time) that haven't been
    addressed yet → send targeted information addressing those concerns.
    """
    if (inputs.has_unaddressed_objections
            and inputs.last_detected_intent not in ("interested", "scheduling", "declining")
            and "cost" not in inputs.objection_topics):  # cost handled by financial rule
        topics_str = ", ".join(inputs.objection_topics)
        channel = "sms" if inputs.has_phone else ("email" if inputs.has_email else "voice")
        return NBAResult(
            action="sms",
            channel=channel,
            priority="normal",
            reasoning=(
                f"Lead has unaddressed objections about: {topics_str}. "
                f"Send targeted information via {channel} that directly addresses "
                "these concerns. Specific objection handling converts better than generic follow-ups."
            ),
            rule_name="address_objections",
            scheduled_for=_now() + timedelta(hours=12),
        )
    return None


def _rule_pending_decision_maker(inputs: PolicyInputs) -> NBAResult | None:
    """
    Another family decision-maker (spouse, grandparent) needs to be involved.
    → Suggest a family-friendly touchpoint rather than a hard close.
    """
    if (inputs.has_pending_decision_makers
            and inputs.last_detected_intent in ("considering", "interested")
            and inputs.total_interactions >= 2):
        return NBAResult(
            action="call",
            channel="voice",
            priority="normal",
            reasoning=(
                "Another decision-maker in the family hasn't been engaged yet. "
                "Suggest a time when the whole family can discuss, or offer to send "
                "information they can share. Pushing for a close without all decision-makers "
                "on board risks a reversal."
            ),
            rule_name="engage_decision_maker",
            scheduled_for=_now() + timedelta(hours=24),
        )
    return None


def _rule_sibling_opportunity(inputs: PolicyInputs) -> NBAResult | None:
    """
    Lead has other children who might also enroll → mention multi-child options.
    Only fires after initial engagement is positive (don't upsell on a cold lead).
    """
    if (inputs.has_siblings
            and inputs.last_detected_intent in ("interested", "scheduling")
            and inputs.last_sentiment == "positive"):
        return NBAResult(
            action="call",
            channel="voice",
            priority="normal",
            reasoning=(
                "Lead has expressed interest AND has siblings who might also enroll. "
                "Mention multi-child discounts or sibling programs during the next call. "
                "This is a high-value expansion opportunity — but only bring it up naturally, "
                "don't lead with it."
            ),
            rule_name="sibling_opportunity",
            scheduled_for=_now() + timedelta(hours=4),
        )
    return None


# ─── Engagement-Based Follow-Up Rules ────────────────────────────────────────

def _rule_positive_engagement(inputs: PolicyInputs) -> NBAResult | None:
    """Positive sentiment / interested → follow up promptly."""
    if inputs.last_detected_intent == "interested" and inputs.last_sentiment == "positive":
        return NBAResult(
            action="call",
            channel="voice",
            priority="high",
            reasoning=(
                "Lead showed positive interest. Follow up with a voice call to deepen "
                "engagement and move toward scheduling."
            ),
            rule_name="positive_engagement",
            scheduled_for=_now() + timedelta(hours=4),
        )
    return None


def _rule_considering(inputs: PolicyInputs) -> NBAResult | None:
    """Lead is on the fence → gentle SMS nudge."""
    if inputs.last_detected_intent == "considering":
        return NBAResult(
            action="sms",
            channel="sms",
            priority="normal",
            reasoning=(
                "Lead is considering but hasn't committed. Send a friendly SMS with "
                "key benefits and a soft call-to-action. Avoid being pushy."
            ),
            rule_name="considering_nudge",
            scheduled_for=_now() + timedelta(hours=24),
        )
    return None


def _rule_objecting(inputs: PolicyInputs) -> NBAResult | None:
    """Lead has objections → address with information, not pressure."""
    if inputs.last_detected_intent in ("objecting", "declining") and inputs.last_sentiment == "negative":
        total_attempts = inputs.total_interactions
        if total_attempts >= django_settings.ESCALATION_AFTER_FAILED_ATTEMPTS:
            return NBAResult(
                action="no_action",
                channel=None,
                priority="low",
                reasoning=(
                    f"Lead has declined/objected after {total_attempts} interactions. "
                    "Respect their decision. No further outreach."
                ),
                rule_name="objection_terminal",
            )
        return NBAResult(
            action="sms",
            channel="sms",
            priority="low",
            reasoning=(
                "Lead expressed objections. Wait 48 hours, then send a low-pressure SMS "
                "addressing common concerns. Do not call — respect boundaries."
            ),
            rule_name="objection_soft_follow_up",
            scheduled_for=_now() + timedelta(hours=48),
        )
    return None


# ─── Channel / Retry Mechanics ───────────────────────────────────────────────

def _rule_channel_escalation(inputs: PolicyInputs) -> NBAResult | None:
    """After N failed attempts on one channel, switch to another."""
    max_per_channel = django_settings.MAX_ATTEMPTS_PER_CHANNEL

    if inputs.total_voice_attempts >= max_per_channel and inputs.last_interaction_channel == "voice":
        if inputs.has_phone and inputs.total_sms_attempts < max_per_channel:
            return NBAResult(
                action="sms",
                channel="sms",
                priority="normal",
                reasoning=(
                    f"Voice calls haven't connected after {inputs.total_voice_attempts} attempts. "
                    "Switching to SMS — less intrusive, lead can respond at their convenience."
                ),
                rule_name="channel_escalation_to_sms",
                scheduled_for=_now() + timedelta(hours=12),
            )
        elif inputs.has_email and inputs.total_email_attempts < max_per_channel:
            return NBAResult(
                action="email",
                channel="email",
                priority="normal",
                reasoning=(
                    f"Voice and SMS haven't worked. Trying email as a last-resort channel."
                ),
                rule_name="channel_escalation_to_email",
                scheduled_for=_now() + timedelta(hours=24),
            )

    if inputs.total_sms_attempts >= max_per_channel and inputs.last_interaction_channel == "sms":
        if inputs.has_phone and inputs.total_voice_attempts < max_per_channel:
            return NBAResult(
                action="call",
                channel="voice",
                priority="normal",
                reasoning=(
                    f"SMS hasn't gotten responses after {inputs.total_sms_attempts} attempts. "
                    "Trying a voice call — more personal touch may break through."
                ),
                rule_name="channel_escalation_to_voice",
                scheduled_for=_now() + timedelta(hours=12),
            )
    return None


def _rule_voicemail_follow_up(inputs: PolicyInputs) -> NBAResult | None:
    """Left a voicemail → wait, then try SMS."""
    if inputs.last_interaction_status == "voicemail":
        return NBAResult(
            action="sms",
            channel="sms",
            priority="normal",
            reasoning=(
                "Left a voicemail. Follow up with an SMS in 4 hours — "
                "reinforces the voicemail and gives an easy way to respond."
            ),
            rule_name="voicemail_sms_follow_up",
            scheduled_for=_now() + timedelta(hours=4),
        )
    return None


def _rule_no_answer_retry(inputs: PolicyInputs) -> NBAResult | None:
    """No answer → retry after cooldown."""
    if inputs.last_interaction_status == "no_answer":
        cooldown = django_settings.COOLDOWN_HOURS_AFTER_NO_RESPONSE
        channel = inputs.last_interaction_channel or "voice"
        return NBAResult(
            action="call" if channel == "voice" else channel,
            channel=channel,
            priority="normal",
            reasoning=(
                f"No answer on last attempt. Retry via {channel} after "
                f"{cooldown}-hour cooldown to avoid being intrusive."
            ),
            rule_name="no_answer_retry",
            scheduled_for=_now() + timedelta(hours=cooldown),
        )
    return None


def _rule_cool_down(inputs: PolicyInputs) -> NBAResult | None:
    """If we contacted them very recently, wait."""
    if inputs.hours_since_last_interaction is not None and inputs.hours_since_last_interaction < 4:
        return NBAResult(
            action="wait",
            channel=None,
            priority="low",
            reasoning=(
                f"Last interaction was only {inputs.hours_since_last_interaction:.1f} hours ago. "
                "Waiting before next contact to avoid over-contacting."
            ),
            rule_name="cool_down",
            scheduled_for=_now() + timedelta(hours=4),
        )
    return None


# ─── Initial / Default Rules ────────────────────────────────────────────────

def _rule_new_lead(inputs: PolicyInputs) -> NBAResult | None:
    """Brand new lead with no interactions → initial outreach."""
    if inputs.lead_status == "new" and inputs.total_interactions == 0:
        channel = inputs.preferred_channel or ("voice" if inputs.has_phone else "sms")
        return NBAResult(
            action="call" if channel == "voice" else channel,
            channel=channel,
            priority="high",
            reasoning=(
                f"New lead — no prior contact. Initial outreach via {channel}. "
                "Voice is preferred for first contact (personal touch)."
            ),
            rule_name="new_lead_initial_outreach",
            scheduled_for=_now() + timedelta(hours=1),
        )
    return None


def _rule_default(inputs: PolicyInputs) -> NBAResult | None:
    """Catch-all — schedule a follow up."""
    channel = inputs.preferred_channel or "voice"
    return NBAResult(
        action="call" if channel == "voice" else channel,
        channel=channel,
        priority="normal",
        reasoning=(
            "Standard follow-up. No strong signals detected — continuing outreach "
            f"via {channel} on normal cadence."
        ),
        rule_name="default_follow_up",
        scheduled_for=_now() + timedelta(hours=24),
    )


# ─── Persist NBA Decision ───────────────────────────────────────────────────

def persist_nba_decision(
    lead: Lead,
    result: NBAResult,
    interaction_id: str | None,
    policy_inputs: PolicyInputs,
) -> NBADecision:
    """Save NBA decision and mark previous ones as superseded."""
    # Mark previous current decision as superseded
    superseded_ids = list(
        NBADecision.objects.filter(lead_id=lead.id, is_current=True)
        .values_list("id", flat=True)
    )
    NBADecision.objects.filter(id__in=superseded_ids).update(
        is_current=False, status="superseded"
    )

    # Cancel any pending scheduled actions tied to superseded decisions
    if superseded_ids:
        ScheduledAction.objects.filter(
            nba_decision_id__in=superseded_ids, status="pending"
        ).update(status="cancelled")

    decision = NBADecision.objects.create(
        lead_id=lead.id,
        interaction_id=interaction_id,
        action=result.action,
        channel=result.channel,
        priority=result.priority,
        scheduled_for=result.scheduled_for,
        reasoning=result.reasoning,
        policy_inputs=policy_inputs.to_dict(),
        rule_name=result.rule_name,
        is_current=True,
        status="pending",
    )

    # Create scheduled action if applicable
    if result.scheduled_for and result.action not in ("no_action", "wait"):
        ScheduledAction.objects.create(
            lead_id=lead.id,
            nba_decision_id=decision.id,
            action_type=result.action,
            channel=result.channel or "voice",
            scheduled_at=result.scheduled_for,
            status="pending",
        )

    return decision

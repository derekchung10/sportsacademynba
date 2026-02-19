"""
Next Best Action (NBA) Decisioning Engine — Graph RL

Architecture:
- State: (lead_status, context_bucket) — ~90 discrete states
- Actions: 12 semantic actions (warm_follow_up, scholarship_outreach, etc.)
- Strategy: Q-learning with UCB action selection picks the semantic action
- Tactics: Action brief builder generates content, tone, prep, and message drafts
- Learning: Q-table updates based on lead funnel progression after each interaction

Hard overrides (compliance):
  - declined → no_action
  - opted_out → no_action
  These bypass the RL engine entirely.

Full lifecycle statuses:
  Acquisition: new → contacted → interested → trial → enrolled
  Retention:   enrolled → active → at_risk → inactive
  Terminal:    declined, unresponsive
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
from app.services.rl_engine import encode_state, select_action, filter_valid_actions
from app.services.action_briefs import build_action_brief, ActionBrief

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
        # Enriched context dimensions
        financial_concern_level: str = "none",
        has_unaddressed_objections: bool = False,
        objection_topics: list[str] | None = None,
        has_scheduling_constraints: bool = False,
        has_siblings: bool = False,
        has_pending_decision_makers: bool = False,
        # Open-ended signals
        additional_signals: list[dict] | None = None,
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
        self.financial_concern_level = financial_concern_level
        self.has_unaddressed_objections = has_unaddressed_objections
        self.objection_topics = objection_topics or []
        self.has_scheduling_constraints = has_scheduling_constraints
        self.has_siblings = has_siblings
        self.has_pending_decision_makers = has_pending_decision_makers
        self.additional_signals = additional_signals or []

    def to_dict(self) -> dict:
        return self.__dict__


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── Enriched Context Loading ────────────────────────────────────────────────

def _load_enriched_context(lead_id) -> dict:
    """
    Load accumulated enriched context from artifacts for a lead.
    Returns a dict with financial, scheduling, family, objection, and additional signals.
    """
    CONCERN_LEVEL_ORDER = {"none": 0, "low": 1, "moderate": 2, "high": 3}
    URGENCY_ORDER = {"low": 0, "moderate": 1, "high": 2}

    result = {
        "financial_concern_level": "none",
        "objection_topics": [],
        "has_unaddressed_objections": False,
        "has_scheduling_constraints": False,
        "has_siblings": False,
        "has_pending_decision_makers": False,
        "additional_signals": [],
    }

    signals_by_label = {}

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

            elif artifact.artifact_type == "additional_signals":
                data = json.loads(artifact.content)
                for sig in data:
                    label = sig.get("signal", "unknown")
                    urgency = sig.get("urgency", "low")
                    existing = signals_by_label.get(label)
                    if not existing or URGENCY_ORDER.get(urgency, 0) > URGENCY_ORDER.get(existing.get("urgency", "low"), 0):
                        signals_by_label[label] = sig

        except (json.JSONDecodeError, TypeError):
            continue

    result["additional_signals"] = list(signals_by_label.values())
    return result


def _build_policy_inputs(lead: Lead, last_interaction: Interaction | None) -> PolicyInputs:
    """Build policy inputs from lead state, last interaction, and enriched context."""
    hours_since = None
    if last_interaction and last_interaction.created_at:
        delta = _now() - last_interaction.created_at
        hours_since = delta.total_seconds() / 3600

    enriched = _load_enriched_context(lead.id)

    inputs = PolicyInputs(
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
        financial_concern_level=enriched["financial_concern_level"],
        has_unaddressed_objections=enriched["has_unaddressed_objections"],
        objection_topics=enriched["objection_topics"],
        has_scheduling_constraints=enriched["has_scheduling_constraints"],
        has_siblings=enriched["has_siblings"],
        has_pending_decision_makers=enriched["has_pending_decision_makers"],
        additional_signals=enriched["additional_signals"],
    )

    # Attach lead name for message drafting
    inputs._lead_first_name = lead.first_name
    return inputs


# ─── Hard Overrides (Compliance) ─────────────────────────────────────────────

def _check_hard_overrides(inputs: PolicyInputs) -> ActionBrief | None:
    """
    Compliance rules that bypass the RL engine entirely.
    These are non-negotiable — no amount of learning should override them.
    """
    if inputs.lead_status == "declined":
        return ActionBrief(
            semantic_action="stop",
            channel="none",
            priority="low",
            scheduled_for=None,
            timing_rationale="Family has declined. Respecting their decision.",
            content_directives=[],
            overall_tone="none",
            state=f"{inputs.lead_status}:terminal",
            q_value=0.0,
        )

    if inputs.last_interaction_status == "opted_out":
        return ActionBrief(
            semantic_action="stop",
            channel="none",
            priority="low",
            scheduled_for=None,
            timing_rationale="Lead opted out of communications.",
            content_directives=[],
            overall_tone="none",
            state=f"{inputs.lead_status}:opted_out",
            q_value=0.0,
        )

    return None


# ─── Main Entry Point ────────────────────────────────────────────────────────

def compute_nba(lead: Lead, latest_interaction: Interaction | None = None) -> tuple[ActionBrief, PolicyInputs]:
    """
    Compute the next best action using the graph RL engine.

    1. Build policy inputs (lead state + enriched context)
    2. Check hard overrides (compliance)
    3. Encode state for RL
    4. Filter valid actions for this state
    5. Select best action via UCB
    6. Build full action brief with content, tone, prep, timing

    Returns (ActionBrief, PolicyInputs) for persistence.
    """
    last_interaction = latest_interaction or (
        Interaction.objects
        .filter(lead_id=lead.id)
        .order_by("-created_at")
        .first()
    )

    inputs = _build_policy_inputs(lead, last_interaction)

    # Hard overrides bypass RL
    override = _check_hard_overrides(inputs)
    if override:
        logger.info("Hard override: %s for lead %s", override.semantic_action, lead.id)
        return override, inputs

    # Encode state and select action via RL
    state = encode_state(inputs)
    valid_actions = filter_valid_actions(state, inputs)
    semantic_action, q_value = select_action(state, valid_actions)

    logger.info(
        "RL selected: action=%s, state=%s, q=%.4f for lead %s",
        semantic_action, state, q_value, lead.id,
    )

    # Build the full action brief
    brief = build_action_brief(semantic_action, inputs, state, q_value)

    return brief, inputs


# ─── Persist NBA Decision ───────────────────────────────────────────────────

def persist_nba_decision(
    lead: Lead,
    brief: ActionBrief,
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
        action=brief.semantic_action,
        channel=brief.channel if brief.channel != "none" else None,
        priority=brief.priority,
        scheduled_for=brief.scheduled_for,
        reasoning=brief.timing_rationale,
        policy_inputs=policy_inputs.to_dict(),
        rule_name=f"rl:{brief.semantic_action}",
        is_current=True,
        status="pending",
        action_brief=brief.to_dict(),
        signal_scores=brief.signal_context,
        rl_state=brief.state,
        rl_q_value=brief.q_value,
    )

    # Create scheduled action if applicable
    if brief.scheduled_for and brief.semantic_action not in ("stop", "wait"):
        ScheduledAction.objects.create(
            lead_id=lead.id,
            nba_decision_id=decision.id,
            action_type=brief.semantic_action,
            channel=brief.channel if brief.channel != "none" else "sms",
            scheduled_at=brief.scheduled_for,
            status="pending",
            payload=brief.to_dict(),
        )

    return decision

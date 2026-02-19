"""
Graph Reinforcement Learning Engine

Models the lead lifecycle as a state-transition graph and learns optimal
actions via tabular Q-learning with UCB action selection.

State: (lead_status, context_bucket) — ~90 discrete states
Actions: 12 semantic actions (not raw channels)
Learning: Q-learning with reward based on lead funnel progression
Exploration: UCB (Upper Confidence Bound) — no random actions on real leads
"""
import logging
import math
from datetime import datetime, timezone

from django.db import transaction

from app.models.q_value import QValue
from app.models.state_transition import StateTransition

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

ALPHA = 0.1    # Learning rate
GAMMA = 0.9    # Discount factor — how much we value future rewards
UCB_C = 1.0    # Exploration coefficient

SEMANTIC_ACTIONS = [
    "warm_follow_up",
    "scheduling_push",
    "scholarship_outreach",
    "info_send",
    "gentle_nudge",
    "objection_address",
    "welcome_onboard",
    "retention_check_in",
    "family_engage",
    "channel_switch",
    "wait",
    "stop",
]

# Rewards for state transitions — keyed by (from_status, to_status)
TRANSITION_REWARDS = {
    ("new", "contacted"): 0.1,
    ("contacted", "interested"): 0.4,
    ("interested", "trial"): 0.7,
    ("trial", "enrolled"): 1.0,
    ("enrolled", "active"): 0.3,
    ("active", "at_risk"): -0.5,
    ("at_risk", "inactive"): -0.7,
    ("at_risk", "active"): 0.5,
    ("inactive", "at_risk"): 0.3,
    ("inactive", "active"): 0.6,
}

# Any transition to declined is heavily penalized
DECLINED_REWARD = -1.0

# Same state → same state: small penalty to encourage progress
STALL_REWARD = -0.02


# ─── State Encoding ──────────────────────────────────────────────────────────

def encode_state(inputs) -> str:
    """
    Encode PolicyInputs into a discrete state string.
    Format: "lead_status:context_bucket"
    """
    status = inputs.lead_status

    if inputs.last_interaction_status in ("no_answer", "voicemail"):
        context = "unreached"
    elif inputs.last_detected_intent in ("declining",) and inputs.last_sentiment == "negative":
        context = "negative"
    elif inputs.last_detected_intent == "scheduling":
        context = "scheduling_intent"
    elif inputs.last_detected_intent == "interested" and inputs.last_sentiment == "positive":
        context = "positive_engagement"
    elif inputs.financial_concern_level in ("moderate", "high"):
        context = "financial_concern"
    elif inputs.has_unaddressed_objections:
        context = "has_objections"
    elif inputs.has_pending_decision_makers or inputs.has_siblings:
        context = "family_context"
    elif inputs.last_detected_intent == "considering":
        context = "considering"
    elif inputs.additional_signals and any(
        s.get("urgency") in ("moderate", "high") for s in inputs.additional_signals
    ):
        context = "novel_signal"
    else:
        context = "neutral"

    return f"{status}:{context}"


# ─── Q-Table Operations ──────────────────────────────────────────────────────

def get_q_value(state: str, action: str) -> QValue:
    """Get or create a Q-table entry."""
    obj, _ = QValue.objects.get_or_create(
        state=state, action=action,
        defaults={"q_value": 0.0, "visit_count": 0, "total_reward": 0.0},
    )
    return obj


def get_all_q_values(state: str) -> dict[str, QValue]:
    """Load all Q-values for a state, creating missing entries with defaults."""
    existing = {q.action: q for q in QValue.objects.filter(state=state)}
    result = {}
    for action in SEMANTIC_ACTIONS:
        if action in existing:
            result[action] = existing[action]
        else:
            result[action] = QValue(
                state=state, action=action,
                q_value=0.0, visit_count=0, total_reward=0.0,
            )
    return result


def get_max_q(state: str) -> float:
    """Return the maximum Q-value achievable from a state (for Bellman update)."""
    max_q = QValue.objects.filter(state=state).order_by("-q_value").values_list("q_value", flat=True).first()
    return max_q if max_q is not None else 0.0


# ─── Action Selection (UCB) ──────────────────────────────────────────────────

def select_action(state: str, available_actions: list[str] | None = None) -> tuple[str, float]:
    """
    Select the best action using Upper Confidence Bound.
    Returns (action_name, q_value).
    """
    actions = available_actions or SEMANTIC_ACTIONS
    q_values = get_all_q_values(state)

    total_visits = sum(q_values[a].visit_count for a in actions if a in q_values)

    best_action = actions[0]
    best_score = -float("inf")
    best_q = 0.0

    for action in actions:
        q = q_values.get(action)
        if q is None:
            exploitation = 0.0
            visit_count = 0
        else:
            exploitation = q.q_value
            visit_count = q.visit_count

        # UCB exploration bonus: under-tried actions get a boost
        if visit_count == 0:
            exploration = UCB_C * 2.0  # High bonus for untried actions
        else:
            exploration = UCB_C * math.sqrt(math.log(total_visits + 1) / visit_count)

        ucb_score = exploitation + exploration

        if ucb_score > best_score:
            best_score = ucb_score
            best_action = action
            best_q = exploitation

    return best_action, best_q


def filter_valid_actions(state: str, inputs) -> list[str]:
    """
    Filter the action space to only actions that make sense in the current state.
    Prevents nonsensical choices (e.g., welcome_onboard for a new lead).
    """
    status = inputs.lead_status
    valid = list(SEMANTIC_ACTIONS)

    # welcome_onboard only for enrolled
    if status != "enrolled":
        valid = [a for a in valid if a != "welcome_onboard"]

    # retention_check_in only for active/at_risk/inactive
    if status not in ("active", "at_risk", "inactive"):
        valid = [a for a in valid if a != "retention_check_in"]

    # family_engage only if we know there are family members to engage
    if not inputs.has_pending_decision_makers and not inputs.has_siblings:
        valid = [a for a in valid if a != "family_engage"]

    # scholarship_outreach only if financial signals exist
    if inputs.financial_concern_level == "none":
        valid = [a for a in valid if a != "scholarship_outreach"]

    # objection_address only if objections exist
    if not inputs.has_unaddressed_objections:
        valid = [a for a in valid if a != "objection_address"]

    # scheduling_push needs a phone or at least some channel
    if not inputs.has_phone and not inputs.has_email:
        valid = [a for a in valid if a not in ("scheduling_push", "warm_follow_up", "retention_check_in")]

    # stop only if we've made significant attempts
    if inputs.total_interactions < 3:
        valid = [a for a in valid if a != "stop"]

    # Always keep at least wait and one contact action
    if not valid:
        valid = ["wait", "gentle_nudge"]

    return valid


# ─── Q-Update (Bellman) ──────────────────────────────────────────────────────

def compute_reward(status_before: str, status_after: str) -> float:
    """Compute the reward for a state transition."""
    if status_after == "declined":
        return DECLINED_REWARD

    if status_before == status_after:
        return STALL_REWARD

    return TRANSITION_REWARDS.get((status_before, status_after), 0.0)


def update_q_table(
    lead_id,
    nba_decision_id,
    state_before: str,
    action_taken: str,
    state_after: str,
    status_before: str,
    status_after: str,
) -> StateTransition | None:
    """
    Perform a Q-learning update after observing a state transition.
    Returns the logged StateTransition, or None if no update was needed.
    """
    reward = compute_reward(status_before, status_after)

    # Bellman update: Q(s,a) = Q(s,a) + α * (r + γ * max_a'Q(s',a') - Q(s,a))
    max_q_next = get_max_q(state_after)

    with transaction.atomic():
        q_entry = get_q_value(state_before, action_taken)
        old_q = q_entry.q_value

        td_target = reward + GAMMA * max_q_next
        td_error = td_target - old_q
        new_q = old_q + ALPHA * td_error

        q_entry.q_value = new_q
        q_entry.visit_count += 1
        q_entry.total_reward += reward
        q_entry.save()

        transition = StateTransition.objects.create(
            lead_id=lead_id,
            nba_decision_id=nba_decision_id,
            state_before=state_before,
            action_taken=action_taken,
            state_after=state_after,
            reward=reward,
            q_value_before=old_q,
            q_value_after=new_q,
        )

    logger.info(
        "Q-update: Q(%s, %s) %.4f -> %.4f (reward=%.2f, td_error=%.4f)",
        state_before, action_taken, old_q, new_q, reward, td_error,
    )

    return transition

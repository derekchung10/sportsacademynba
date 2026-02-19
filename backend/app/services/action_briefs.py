"""
Action Brief Builder

The RL engine picks the strategy (which semantic action). This module generates
the tactics: what to say, how to say it, what to prepare, what to avoid.

Each semantic action has a base template. The builder enriches it with
context signals from the lead's accumulated artifacts (financial concerns,
objections, family context, additional signals, etc.).
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


@dataclass
class ActionBrief:
    semantic_action: str
    channel: str
    priority: str
    scheduled_for: datetime | None
    timing_rationale: str

    content_directives: list[dict] = field(default_factory=list)
    overall_tone: str = "informational"
    info_to_prepare: list[str] = field(default_factory=list)
    things_to_avoid: list[str] = field(default_factory=list)
    message_draft: str | None = None

    # Auditability
    state: str = ""
    q_value: float = 0.0
    signal_context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "semantic_action": self.semantic_action,
            "channel": self.channel,
            "priority": self.priority,
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
            "timing_rationale": self.timing_rationale,
            "content_directives": self.content_directives,
            "overall_tone": self.overall_tone,
            "info_to_prepare": self.info_to_prepare,
            "things_to_avoid": self.things_to_avoid,
            "message_draft": self.message_draft,
            "state": self.state,
            "q_value": self.q_value,
            "signal_context": self.signal_context,
        }


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── Brief Templates ─────────────────────────────────────────────────────────

BRIEF_TEMPLATES = {
    "warm_follow_up": {
        "channel": "voice",
        "base_tone": "enthusiastic",
        "base_timing_hours": 4,
        "timing_rationale": "Call during evening hours when the parent is likely available and not rushed",
        "base_directives": [
            {"point": "Ask about the child by name — show you remember them", "priority": 1},
            {"point": "Share what a first session looks like and what to expect", "priority": 2},
            {"point": "Listen more than talk — let them express what matters to them", "priority": 3},
        ],
        "base_info_to_prepare": ["upcoming class schedule", "coach bio and credentials"],
        "base_things_to_avoid": ["don't hard-sell or push for commitment", "don't rush to schedule if they're not ready"],
    },
    "scheduling_push": {
        "channel": "voice",
        "base_tone": "enthusiastic",
        "base_timing_hours": 1,
        "timing_rationale": "Act quickly while scheduling intent is fresh — strike within the hour",
        "base_directives": [
            {"point": "Reference their expressed interest in scheduling", "priority": 1},
            {"point": "Offer 2-3 specific time slots rather than 'when works for you'", "priority": 2},
            {"point": "Confirm what the child should bring and what to expect", "priority": 3},
        ],
        "base_info_to_prepare": ["available trial/visit time slots", "location and parking details", "what to bring list"],
        "base_things_to_avoid": ["don't offer too many options — decision fatigue kills conversion", "don't make them feel locked in"],
    },
    "scholarship_outreach": {
        "channel": "sms",
        "base_tone": "empathetic",
        "base_timing_hours": 2,
        "timing_rationale": "Send written info so they can review financial options at their own pace before a call",
        "base_directives": [
            {"point": "Share specific scholarship/financial aid options available", "priority": 1},
            {"point": "Include concrete numbers — not vague 'affordable' language", "priority": 2},
            {"point": "Mention application process and any deadlines", "priority": 3},
        ],
        "base_info_to_prepare": ["scholarship application link", "payment plan breakdown", "financial aid contact"],
        "base_things_to_avoid": ["don't lead with full sticker price", "avoid implying they can't afford it", "no pressure about deadlines"],
    },
    "info_send": {
        "channel": "sms",
        "base_tone": "informational",
        "base_timing_hours": 2,
        "timing_rationale": "Send requested info promptly while the question is still top of mind",
        "base_directives": [
            {"point": "Directly answer the specific questions they asked", "priority": 1},
            {"point": "Include a clear next step (visit, call, trial class)", "priority": 2},
            {"point": "Keep it concise — a wall of text won't get read", "priority": 3},
        ],
        "base_info_to_prepare": ["program details relevant to their child's age and sport", "schedule and pricing overview"],
        "base_things_to_avoid": ["don't overload with information they didn't ask for", "don't skip their actual question to pitch"],
    },
    "gentle_nudge": {
        "channel": "sms",
        "base_tone": "gentle",
        "base_timing_hours": 24,
        "timing_rationale": "Wait a full day — give them space to think without feeling pressured",
        "base_directives": [
            {"point": "Keep it short and friendly — one sentence plus a soft CTA", "priority": 1},
            {"point": "Reference something specific from the last conversation to show you listened", "priority": 2},
            {"point": "Make it easy to respond (yes/no question, not open-ended)", "priority": 3},
        ],
        "base_info_to_prepare": ["notes from last interaction"],
        "base_things_to_avoid": ["don't repeat what you already said", "don't use 'just checking in' — be specific", "no guilt language"],
    },
    "objection_address": {
        "channel": "sms",
        "base_tone": "empathetic",
        "base_timing_hours": 12,
        "timing_rationale": "Give time to prepare a thoughtful response rather than a reactive one",
        "base_directives": [
            {"point": "Acknowledge their concern directly — don't brush it off", "priority": 1},
            {"point": "Provide specific facts/evidence that address the concern", "priority": 2},
            {"point": "Offer to discuss further if they want — don't assume one message resolves it", "priority": 3},
        ],
        "base_info_to_prepare": ["safety record and certifications", "testimonials from families with similar concerns"],
        "base_things_to_avoid": ["don't dismiss their concern", "don't say 'but' after acknowledging — use 'and'", "don't get defensive"],
    },
    "welcome_onboard": {
        "channel": "sms",
        "base_tone": "enthusiastic",
        "base_timing_hours": 2,
        "timing_rationale": "Send welcome info promptly after enrollment to reinforce their decision",
        "base_directives": [
            {"point": "Congratulate them and express excitement about having the child join", "priority": 1},
            {"point": "Share practical first-day details: schedule, location, what to bring", "priority": 2},
            {"point": "Introduce the coach or point of contact by name", "priority": 3},
        ],
        "base_info_to_prepare": ["first session date and time", "what to bring checklist", "coach name and photo", "parent FAQ"],
        "base_things_to_avoid": ["don't upsell additional programs yet", "don't overwhelm with admin details"],
    },
    "retention_check_in": {
        "channel": "voice",
        "base_tone": "warm",
        "base_timing_hours": 48,
        "timing_rationale": "Don't rush — a retention call feels more genuine with a natural cadence, not reactive",
        "base_directives": [
            {"point": "Ask how the child is enjoying the program — genuinely listen", "priority": 1},
            {"point": "Share a specific positive observation about the child's progress if available", "priority": 2},
            {"point": "Ask if there's anything the academy can do better", "priority": 3},
        ],
        "base_info_to_prepare": ["child's attendance history", "any coach feedback", "upcoming events or milestones"],
        "base_things_to_avoid": ["don't make it feel like a survey", "don't mention payment or renewals", "don't ignore complaints"],
    },
    "family_engage": {
        "channel": "voice",
        "base_tone": "warm",
        "base_timing_hours": 24,
        "timing_rationale": "Suggest a time when the whole family can talk — evenings or weekends",
        "base_directives": [
            {"point": "Acknowledge that this is a family decision, not just one parent's", "priority": 1},
            {"point": "Offer to have the other decision-maker join the next call or visit", "priority": 2},
            {"point": "Provide materials they can share with the other parent", "priority": 3},
        ],
        "base_info_to_prepare": ["program overview PDF suitable for sharing", "FAQ for skeptical family members"],
        "base_things_to_avoid": ["don't pressure the current contact to 'convince' the other parent", "don't bypass the decision-maker"],
    },
    "channel_switch": {
        "channel": "sms",  # default switch-to; will be overridden by builder
        "base_tone": "informational",
        "base_timing_hours": 12,
        "timing_rationale": "Previous channel hasn't worked — try a different one to break through",
        "base_directives": [
            {"point": "Briefly re-introduce yourself and the academy", "priority": 1},
            {"point": "Reference that you've tried to reach them (without guilt)", "priority": 2},
            {"point": "Make it easy to respond on this new channel", "priority": 3},
        ],
        "base_info_to_prepare": ["summary of previous outreach attempts"],
        "base_things_to_avoid": ["don't say 'I've been trying to reach you'", "don't repeat the exact same pitch"],
    },
    "wait": {
        "channel": "none",
        "base_tone": "none",
        "base_timing_hours": 48,
        "timing_rationale": "Strategically give space — sometimes silence is more effective than another touchpoint",
        "base_directives": [],
        "base_info_to_prepare": [],
        "base_things_to_avoid": [],
    },
    "stop": {
        "channel": "none",
        "base_tone": "none",
        "base_timing_hours": 0,
        "timing_rationale": "Cease outreach — further contact is unlikely to help and may damage the relationship",
        "base_directives": [],
        "base_info_to_prepare": [],
        "base_things_to_avoid": [],
    },
}


# ─── Context Enrichment Rules ────────────────────────────────────────────────
# These add extra directives based on the lead's accumulated context signals,
# regardless of which semantic action was chosen.

def _enrich_with_context(brief: ActionBrief, inputs) -> None:
    """Add context-specific directives based on lead's accumulated signals."""
    directives = brief.content_directives
    prepare = brief.info_to_prepare
    avoid = brief.things_to_avoid

    if brief.semantic_action in ("wait", "stop"):
        return

    # Financial concern context
    if inputs.financial_concern_level in ("moderate", "high") and brief.semantic_action != "scholarship_outreach":
        directives.append({
            "point": "Be mindful of cost — if pricing comes up, mention financial aid options",
            "priority": 5, "signal": "financial_concern",
        })
        avoid.append("don't casually mention fees or premium options")

    # Sibling context
    if inputs.has_siblings and brief.semantic_action not in ("stop", "wait"):
        directives.append({
            "point": "If conversation goes well, naturally mention sibling/family programs",
            "priority": 6, "signal": "sibling_opportunity",
        })
        avoid.append("don't lead with the upsell — mention siblings only if it flows naturally")

    # Pending decision-makers
    if inputs.has_pending_decision_makers and brief.semantic_action != "family_engage":
        directives.append({
            "point": "Ask if the other decision-maker has any questions — offer to include them",
            "priority": 5, "signal": "pending_decision_maker",
        })

    # Scheduling constraints
    if inputs.has_scheduling_constraints:
        directives.append({
            "point": "Reference their scheduling constraints — show you remember and have worked around them",
            "priority": 4, "signal": "scheduling_constraints",
        })
        prepare.append("alternative schedule options that fit their constraints")

    # Objection context (when not the primary action)
    if inputs.has_unaddressed_objections and brief.semantic_action != "objection_address":
        topics = ", ".join(inputs.objection_topics) if inputs.objection_topics else "unspecified"
        directives.append({
            "point": f"Be ready to address concerns about: {topics}",
            "priority": 5, "signal": "unaddressed_objection",
        })

    # Additional signals (open-ended)
    for sig in inputs.additional_signals:
        urgency = sig.get("urgency", "low")
        if urgency in ("moderate", "high"):
            suggested = sig.get("suggested_action", "")
            signal_name = sig.get("signal", "unknown")
            directives.append({
                "point": suggested or f"Address '{signal_name}' signal detected in previous conversation",
                "priority": 4 if urgency == "high" else 6,
                "signal": signal_name,
            })


def _determine_channel(semantic_action: str, inputs) -> str:
    """Determine the actual channel, respecting availability and preferences."""
    template = BRIEF_TEMPLATES.get(semantic_action, {})
    base_channel = template.get("channel", "sms")

    if base_channel == "none":
        return "none"

    if semantic_action == "channel_switch":
        # Pick the channel we've used LEAST
        attempts = {
            "voice": inputs.total_voice_attempts,
            "sms": inputs.total_sms_attempts,
            "email": inputs.total_email_attempts,
        }
        available = {}
        if inputs.has_phone:
            available["voice"] = attempts["voice"]
            available["sms"] = attempts["sms"]
        if inputs.has_email:
            available["email"] = attempts["email"]
        if available:
            return min(available, key=available.get)
        return "sms"

    # Respect preferred channel if set
    if inputs.preferred_channel:
        if base_channel == "voice" and inputs.preferred_channel in ("sms", "email"):
            return inputs.preferred_channel
        if base_channel == "sms" and inputs.preferred_channel == "email":
            return "email"

    # Fall back to what's available
    if base_channel == "voice" and not inputs.has_phone:
        return "email" if inputs.has_email else "sms"
    if base_channel == "sms" and not inputs.has_phone:
        return "email" if inputs.has_email else "voice"
    if base_channel == "email" and not inputs.has_email:
        return "sms" if inputs.has_phone else "voice"

    return base_channel


def _determine_priority(q_value: float, semantic_action: str, inputs=None) -> str:
    """
    Derive priority from context signals, action type, and Q-value.
    Context-based heuristics ensure meaningful priorities even with
    fresh Q-tables (where all values start near zero).
    """
    # Urgent: scheduling intent is hot, or Q-value is very high
    if semantic_action == "scheduling_push":
        return "high"
    if q_value > 0.5:
        return "high"

    # High: at-risk retention, objection handling, win-back
    if semantic_action in ("objection_address", "retention_check_in", "channel_switch"):
        return "high"
    if inputs and getattr(inputs, "lead_status", "") in ("at_risk",):
        return "high"

    # Normal: active engagement, financial outreach, welcome
    if semantic_action in ("warm_follow_up", "scholarship_outreach", "welcome_onboard", "family_engage"):
        return "normal"
    if inputs and getattr(inputs, "lead_status", "") in ("interested", "trial", "enrolled"):
        return "normal"
    if q_value > 0.2:
        return "normal"

    # Low: gentle nudges, stop, wait, or new leads with no urgency
    return "low"


def _contextualize_rationale(brief: ActionBrief, inputs) -> None:
    """
    Replace the generic timing_rationale with a sentence informed by the
    lead's actual context: child info, scheduling constraints, response
    timestamps, and conversation history.
    """
    action = brief.semantic_action
    if action in ("wait", "stop"):
        return

    child = getattr(inputs, "_lead_child_name", None) or "their child"
    sport = getattr(inputs, "_lead_sport", None) or ""
    name = getattr(inputs, "_lead_first_name", "them")
    timing = getattr(inputs, "_response_timing", {})
    time_hint = timing.get("time_hint")
    channel = brief.channel

    # Channel verb that reads naturally in a sentence
    ch = {"voice": "call", "sms": "text", "email": "email"}.get(channel, "reach out to")

    # Build the core suggestion with the medium woven in
    core = {
        "scheduling_push": f"{ch.capitalize()} {name} now while they're ready to schedule",
        "warm_follow_up": f"{ch.capitalize()} {name} to keep the conversation going",
        "gentle_nudge": f"{ch.capitalize()} {name} with a light check-in",
        "scholarship_outreach": f"{ch.capitalize()} {name} with financial aid details they can review at their own pace",
        "info_send": f"{ch.capitalize()} {name} with the information they asked about",
        "objection_address": f"{ch.capitalize()} {name} to address {', '.join(inputs.objection_topics) if inputs.objection_topics else 'their concerns'}",
        "welcome_onboard": f"{ch.capitalize()} {name} with a welcome message and first-day details for {child}",
        "retention_check_in": f"{ch.capitalize()} {name} to check in on how {child} is doing",
        "family_engage": f"{ch.capitalize()} {name} when the whole family can talk",
        "channel_switch": f"Try a {ch} instead — previous channel hasn't connected with {name}",
    }.get(action, f"{ch.capitalize()} {name}")

    extras = []

    # Timing from actual response patterns
    if time_hint:
        extras.append(f"they tend to respond {time_hint}")

    # Context clues
    if inputs.has_scheduling_constraints:
        extras.append("mention the alternative schedule options")
    if inputs.has_pending_decision_makers:
        extras.append("include info they can share with the other decision-maker")
    if inputs.financial_concern_level in ("moderate", "high") and action != "scholarship_outreach":
        extras.append("be prepared to discuss financial options")

    # Sport/child personalization
    if sport and action in ("warm_follow_up", "retention_check_in", "scheduling_push", "welcome_onboard"):
        extras.append(f"reference {child}'s {sport}")

    if extras:
        brief.timing_rationale = f"{core} — {', '.join(extras)}."
    else:
        brief.timing_rationale = f"{core}."


def _generate_message_draft(brief: ActionBrief, inputs) -> str | None:
    """Generate a template-based message draft for SMS/email actions."""
    if brief.channel not in ("sms", "email") or not brief.content_directives:
        return None

    lead_name = getattr(inputs, "_lead_first_name", "there")

    points = sorted(brief.content_directives, key=lambda d: d.get("priority", 99))
    top_points = points[:2]

    lines = [f"Hi {lead_name},"]
    for p in top_points:
        lines.append(p["point"])

    if brief.semantic_action == "scholarship_outreach":
        lines.append("Would you like me to send over the details?")
    elif brief.semantic_action == "gentle_nudge":
        lines.append("Would you like to chat more about it?")
    elif brief.semantic_action == "info_send":
        lines.append("Let me know if you have any other questions!")
    else:
        lines.append("Looking forward to hearing from you.")

    return "\n\n".join(lines)


# ─── Public API ───────────────────────────────────────────────────────────────

def build_action_brief(
    semantic_action: str,
    inputs,
    state: str,
    q_value: float,
) -> ActionBrief:
    """
    Build a full action brief from a semantic action and context.
    Combines the base template with context-specific enrichment.
    """
    template = BRIEF_TEMPLATES.get(semantic_action)
    if not template:
        logger.warning("Unknown semantic action '%s', falling back to gentle_nudge", semantic_action)
        template = BRIEF_TEMPLATES["gentle_nudge"]
        semantic_action = "gentle_nudge"

    channel = _determine_channel(semantic_action, inputs)
    timing_hours = template["base_timing_hours"]
    priority = _determine_priority(q_value, semantic_action, inputs)

    brief = ActionBrief(
        semantic_action=semantic_action,
        channel=channel,
        priority=priority,
        scheduled_for=_now() + timedelta(hours=timing_hours) if timing_hours > 0 else None,
        timing_rationale=template["timing_rationale"],
        content_directives=[dict(d) for d in template["base_directives"]],
        overall_tone=template["base_tone"],
        info_to_prepare=list(template["base_info_to_prepare"]),
        things_to_avoid=list(template["base_things_to_avoid"]),
        message_draft=None,
        state=state,
        q_value=q_value,
        signal_context={},
    )

    # Enrich with lead-specific context
    _enrich_with_context(brief, inputs)

    # Generate contextual rationale (replaces generic template text)
    _contextualize_rationale(brief, inputs)

    # Sort directives by priority
    brief.content_directives.sort(key=lambda d: d.get("priority", 99))

    # Deduplicate info_to_prepare and things_to_avoid
    brief.info_to_prepare = list(dict.fromkeys(brief.info_to_prepare))
    brief.things_to_avoid = list(dict.fromkeys(brief.things_to_avoid))

    # Build signal context for auditability
    brief.signal_context = _build_signal_context(inputs)

    # Generate message draft for text-based channels
    brief.message_draft = _generate_message_draft(brief, inputs)

    return brief


def _build_signal_context(inputs) -> dict:
    """Snapshot the active signals for auditability."""
    return {
        "lead_status": inputs.lead_status,
        "last_intent": inputs.last_detected_intent,
        "last_sentiment": inputs.last_sentiment,
        "financial_concern_level": inputs.financial_concern_level,
        "has_objections": inputs.has_unaddressed_objections,
        "objection_topics": inputs.objection_topics,
        "has_siblings": inputs.has_siblings,
        "has_pending_decision_makers": inputs.has_pending_decision_makers,
        "has_scheduling_constraints": inputs.has_scheduling_constraints,
        "additional_signals_count": len(inputs.additional_signals),
        "total_interactions": inputs.total_interactions,
    }

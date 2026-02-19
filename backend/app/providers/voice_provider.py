"""
Voice Provider Stub — simulates a voice call provider (e.g., Twilio, Vonage).

This is the "context injection boundary" for voice calls.
Before placing/answering a call, the provider requests a context pack
so the AI agent knows the lead's history and what to discuss.
"""
import logging
from app.services.context_service import assemble_context_pack
from app.utils import utcnow

logger = logging.getLogger(__name__)


class VoiceProvider:
    """Stubbed voice provider that demonstrates the context injection boundary."""

    def __init__(self):
        self.name = "voice_provider_stub"

    def prepare_outbound_call(self, lead_id: str) -> dict:
        """
        Prepare context for an outbound call.
        In production, this would be called by the voice provider SDK
        right before placing the call, passing the context pack to the AI agent.
        """
        context_pack = assemble_context_pack(lead_id)

        call_config = {
            "provider": self.name,
            "action": "outbound_call",
            "lead_id": str(lead_id),
            "context_pack": context_pack,
            "agent_instructions": self._build_agent_instructions(context_pack),
            "prepared_at": utcnow().isoformat(),
        }

        logger.info(f"Prepared outbound call for lead {lead_id}")
        return call_config

    def prepare_inbound_call(self, lead_id: str) -> dict:
        """
        Prepare context for an inbound call.
        In production, triggered by caller-ID lookup when a call comes in.
        The AI agent receives this context pack before answering.
        """
        context_pack = assemble_context_pack(lead_id)

        call_config = {
            "provider": self.name,
            "action": "inbound_call",
            "lead_id": str(lead_id),
            "context_pack": context_pack,
            "agent_instructions": self._build_agent_instructions(context_pack),
            "prepared_at": utcnow().isoformat(),
        }

        logger.info(f"Prepared inbound call context for lead {lead_id}")
        return call_config

    def _build_agent_instructions(self, context: dict) -> str:
        """
        Build the instruction prompt for the AI voice agent.
        This is what the agent would use to guide the conversation.
        """
        lines = [
            f"You are calling {context['lead_name']} about {context.get('campaign_goal') or 'sports academy enrollment'}.",
            f"Current status: {context['current_status']}. Total interactions: {context['interaction_count']}.",
        ]

        if context.get("child_info"):
            lines.append(f"Their child: {context['child_info']}.")

        if context.get("latest_summary"):
            lines.append(f"Last interaction summary: {context['latest_summary']}")

        if context.get("known_facts"):
            lines.append(f"What we know: {'; '.join(context['known_facts'][:5])}")

        if context.get("open_questions"):
            lines.append(f"Open questions to address: {'; '.join(context['open_questions'][:3])}")

        if context.get("current_nba"):
            lines.append(
                f"Recommended approach: {context['current_nba'].get('reasoning', 'Standard follow-up')}"
            )

        return "\n".join(lines)


class SMSProvider:
    """Stubbed SMS provider."""

    def __init__(self):
        self.name = "sms_provider_stub"

    def prepare_outbound_sms(self, lead_id: str) -> dict:
        """Prepare context for an outbound SMS."""
        context_pack = assemble_context_pack(lead_id)

        sms_config = {
            "provider": self.name,
            "action": "outbound_sms",
            "lead_id": str(lead_id),
            "context_pack": context_pack,
            "suggested_message": self._suggest_message(context_pack),
            "prepared_at": utcnow().isoformat(),
        }

        logger.info(f"Prepared outbound SMS for lead {lead_id}")
        return sms_config

    def _suggest_message(self, context: dict) -> str:
        """Generate a suggested SMS message based on context."""
        name = context["lead_name"].split()[0]  # First name
        goal = context.get("campaign_goal") or "our sports academy programs"

        if context["current_status"] == "new":
            return (
                f"Hi {name}! This is the {goal} team. We'd love to chat about "
                f"opportunities for your child. When's a good time to talk?"
            )
        elif context["current_status"] in ("interested", "scheduled"):
            return (
                f"Hi {name}! Following up on our conversation about {goal}. "
                f"Would you like to schedule a visit?"
            )
        else:
            return (
                f"Hi {name}, just checking in about {goal}. "
                f"Happy to answer any questions you might have!"
            )

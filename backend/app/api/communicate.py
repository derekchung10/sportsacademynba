"""
Communication API — operator-initiated outreach (SMS, call, email).

These endpoints let the operator send messages or start calls from the UI.
In production these would integrate with Twilio/Vonage/SendGrid.
In dev mode (COMMS_PROVIDER=mock, the default), they simulate the full
round-trip: send → AI-generated reply → processed interaction.
"""
import random
import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status as drf_status

from app.models.lead import Lead
from app.models.interaction import Interaction
from app.services.interaction_processor import process_interaction

logger = logging.getLogger(__name__)


def _auto_unarchive(lead):
    """Move a lead out of archive when an outbound message is sent."""
    if lead.is_archived:
        lead.is_archived = False
        lead.save(update_fields=["is_archived", "updated_at"])
        from app.models.event import Event
        Event.objects.create(
            lead_id=lead.id,
            event_type="lead_unarchived",
            source="system",
            description="Conversation unarchived (new outbound message)",
        )


# ─── Mock reply generator ──────────────────────────────────────────────────────

MOCK_SMS_REPLIES = {
    # ─── Acquisition statuses ─────────────────────────────
    "new": [
        "Hi! Yes, we saw the flyer. Can you tell me more about the program?",
        "Thanks for reaching out. What ages do you accept?",
        "Not sure yet, what are the costs involved?",
        "Hey! My son has been wanting to try {sport}. What's the schedule like?",
    ],
    "contacted": [
        "Sorry I missed your call earlier. Can you call back tomorrow?",
        "We're interested but need to check our schedule first.",
        "What days do you have practice? My daughter also does dance on Tuesdays.",
        "Can you send me more details about pricing?",
    ],
    "interested": [
        "We talked it over and we're definitely interested!",
        "My husband wants to know if there's a trial class available.",
        "The timing works for us. What's the next step?",
        "Is there a sibling discount? We have two kids who might want to join.",
    ],
    "trial": [
        "{child} had a great time at the trial! We want to sign up.",
        "The trial was fun but {child} wasn't sure about the coach. Can we try another session?",
        "We came to the trial session — {child} loved it! What are the enrollment options?",
        "Great experience at the trial. We need to figure out the schedule before committing.",
    ],
    # ─── Retention statuses ───────────────────────────────
    "enrolled": [
        "Thanks for the welcome! When is the first class?",
        "Got the info. {child} is excited to start!",
        "Quick question — what should {child} bring to the first class?",
        "We're all set! See you at the first session.",
    ],
    "active": [
        "{child} is loving the classes! Thanks for checking in.",
        "All good here! Any tournaments coming up?",
        "Coach mentioned {child} is improving — we're really happy with the program.",
        "Is there a more advanced group {child} could move into?",
    ],
    "at_risk": [
        "Sorry we missed last week — {child} was sick. We'll be back this week.",
        "Things have been hectic. Is it okay to skip a couple weeks?",
        "We've been thinking about whether to continue. The schedule is tough.",
        "Transportation has been hard. Are there any weekend classes?",
    ],
    "inactive": [
        "Oh hi! Sorry we dropped off. Things got busy with school.",
        "We've been meaning to come back. What's the schedule looking like?",
        "To be honest, {child} lost interest. Is there a different program?",
        "Hi, yeah we haven't been around. What's new at the academy?",
    ],
    # ─── Terminal ─────────────────────────────────────────
    "declined": [
        "We appreciate the follow-up but the timing isn't right for us now.",
        "We found another program closer to home. Thanks though!",
        "Maybe next season. Can you reach out again in a few months?",
    ],
    "unresponsive": [
        "Oh hi, sorry I've been busy! What were you calling about?",
        "Sorry, who is this?",
        "Oh right, the {sport} program. Let me think about it.",
    ],
}

MOCK_CALL_TRANSCRIPTS = {
    "positive": [
        "Agent: Hi {name}, this is calling from the academy about {child}'s {sport} program.\n"
        "{name}: Oh hi! Yes, {child} has been really enjoying it.\n"
        "Agent: That's wonderful to hear! We've noticed great progress. Would you be interested in our upcoming showcase?\n"
        "{name}: Absolutely! {child} would love that.\n"
        "Agent: I'll send you the details. Also, we have a referral program if you know any other families.\n"
        "{name}: Actually, my neighbor's kid might be interested. I'll pass along the info.\n"
        "Agent: That would be amazing. Thanks, {name}!",

        "Agent: Hi {name}, this is calling from the academy about our {sport} program for {child}.\n"
        "{name}: Oh hi! Yes, we've been meaning to look into that.\n"
        "Agent: Great! We have sessions on weekdays and weekends. Would you like to come for a free trial?\n"
        "{name}: That sounds perfect. My {child_rel} has been asking about {sport} for months.\n"
        "Agent: Wonderful! I can schedule a trial for this Saturday if that works?\n"
        "{name}: Saturday works great. What time?\n"
        "Agent: We have a 10am session. I'll send you the details.\n"
        "{name}: Perfect, we'll be there. Thanks!",
    ],
    "neutral": [
        "Agent: Hi {name}, calling from the academy about {child}.\n"
        "{name}: Hi. Yeah, {child} has been going but we're not sure about continuing.\n"
        "Agent: I'm sorry to hear that. Is there anything specific we can improve?\n"
        "{name}: Honestly, the schedule is hard with school and other activities.\n"
        "Agent: I totally understand. We actually added some new time slots — Tuesday and Thursday evenings.\n"
        "{name}: Oh, that might work better. Can you send me the updated schedule?\n"
        "Agent: Absolutely, I'll text it over right now.",

        "Agent: Hi {name}, calling from the academy about our {sport} program.\n"
        "{name}: Yeah, I saw the ad. I'm not sure though.\n"
        "Agent: No pressure at all. Can I tell you a bit about what we offer?\n"
        "{name}: Sure, go ahead.\n"
        "Agent: We focus on skill development and fun for kids. The program runs twice a week.\n"
        "{name}: Hmm, how much does it cost?\n"
        "Agent: We have different plans starting from $50/month. Would you like me to send the details?\n"
        "{name}: Yeah, email me the info and I'll discuss with my spouse.",
    ],
    "negative": [
        "Agent: Hi {name}, calling to check in about {child}'s {sport} classes.\n"
        "{name}: Hi. Actually, we've decided to stop coming.\n"
        "Agent: I'm sorry to hear that. Would you mind sharing what changed?\n"
        "{name}: {child} just isn't into it anymore. And the cost adds up.\n"
        "Agent: I completely understand. If things change, we'd love to have {child} back. "
        "We do have financial aid options too.\n"
        "{name}: I'll keep that in mind. Thanks for being understanding.",

        "Agent: Hi {name}, calling about our {sport} program for {child}.\n"
        "{name}: Hi. Look, I appreciate the call but I don't think the timing is right.\n"
        "Agent: I completely understand. Is there anything specific holding you back?\n"
        "{name}: Mainly the cost and {child}'s schedule is already pretty full with school.\n"
        "Agent: That makes sense. We do have flexible scheduling and some scholarship options.\n"
        "{name}: Maybe. Can you call back next month? Things might change.\n"
        "Agent: Absolutely, I'll follow up then. Thanks for your time!",
    ],
    "no_answer": None,
}

MOCK_EMAIL_REPLIES = {
    "interested": (
        "Hi,\n\nThank you for the information about the {sport} program! "
        "We're very interested in getting {child} started. Could you send us the "
        "registration forms and let us know about upcoming class times?\n\n"
        "Best regards,\n{name}"
    ),
    "neutral": (
        "Hi,\n\nThanks for reaching out. We're still considering it. "
        "A couple of questions:\n"
        "- What's the coach-to-student ratio?\n"
        "- Is there a trial class?\n"
        "- What do kids usually wear to practice?\n\n"
        "Thanks,\n{name}"
    ),
    "negative": (
        "Hi,\n\nWe appreciate you following up. Unfortunately {child} has been "
        "too busy with school to continue at the moment. We may revisit next semester.\n\n"
        "Thank you,\n{name}"
    ),
}


def _format_template(template, lead):
    """Fill in template placeholders with lead data."""
    return template.format(
        name=lead.first_name,
        child=lead.child_name or "your child",
        child_rel="son" if random.random() > 0.5 else "daughter",
        sport=lead.sport or "sports",
    )


def _pick_reply_tone(lead):
    """Pick a reply tone based on the lead's current status."""
    if lead.status in ("interested", "scheduled"):
        return random.choice(["positive", "positive", "neutral"])
    if lead.status in ("declined", "unresponsive"):
        return random.choice(["negative", "neutral", "neutral"])
    return random.choice(["positive", "neutral", "neutral", "negative"])


def _create_outbound_interaction(lead, channel, content, duration=None):
    """Create the outbound interaction record."""
    return Interaction.objects.create(
        lead=lead,
        channel=channel,
        direction="outbound",
        status="completed",
        transcript=content,
        duration_seconds=duration,
        started_at=timezone.now(),
        ended_at=timezone.now() + timedelta(seconds=duration or 0),
    )


def _create_inbound_interaction(lead, channel, content, duration=None):
    """Create a mock inbound reply interaction."""
    return Interaction.objects.create(
        lead=lead,
        channel=channel,
        direction="inbound",
        status="completed",
        transcript=content,
        duration_seconds=duration,
        started_at=timezone.now(),
        ended_at=timezone.now() + timedelta(seconds=duration or 0),
    )


class SendSMSView(APIView):
    """Send an SMS to a lead. In mock mode, generates a simulated reply."""

    def post(self, request, lead_id):
        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return Response({"detail": "Lead not found"}, status=drf_status.HTTP_404_NOT_FOUND)

        _auto_unarchive(lead)

        message = request.data.get("message", "").strip()
        if not message:
            return Response({"detail": "Message is required"}, status=drf_status.HTTP_400_BAD_REQUEST)

        # Create outbound SMS interaction
        outbound = _create_outbound_interaction(lead, "sms", message)
        process_interaction(outbound)

        result = {
            "outbound_id": str(outbound.id),
            "message": message,
            "reply": None,
        }

        # In mock mode, simulate a reply after a short "delay"
        if getattr(settings, 'COMMS_PROVIDER', 'mock') == 'mock':
            status_key = lead.status if lead.status in MOCK_SMS_REPLIES else "new"
            replies = MOCK_SMS_REPLIES.get(status_key, MOCK_SMS_REPLIES["new"])
            reply_text = _format_template(random.choice(replies), lead)

            inbound = _create_inbound_interaction(lead, "sms", reply_text)
            process_interaction(inbound)

            result["reply"] = {
                "id": str(inbound.id),
                "message": reply_text,
            }

        return Response(result, status=drf_status.HTTP_201_CREATED)


class MakeCallView(APIView):
    """Initiate a call to a lead. In mock mode, simulates a full conversation."""

    def post(self, request, lead_id):
        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return Response({"detail": "Lead not found"}, status=drf_status.HTTP_404_NOT_FOUND)

        _auto_unarchive(lead)

        result = {"lead_id": str(lead_id)}

        if getattr(settings, 'COMMS_PROVIDER', 'mock') == 'mock':
            tone = _pick_reply_tone(lead)

            # Sometimes calls go unanswered
            if random.random() < 0.15:
                no_answer = Interaction.objects.create(
                    lead=lead,
                    channel="voice",
                    direction="outbound",
                    status="no_answer",
                    transcript=None,
                    duration_seconds=0,
                    started_at=timezone.now(),
                    ended_at=timezone.now(),
                )
                process_interaction(no_answer)
                result["status"] = "no_answer"
                result["interaction_id"] = str(no_answer.id)
                return Response(result, status=drf_status.HTTP_201_CREATED)

            # Generate a conversation transcript
            templates = MOCK_CALL_TRANSCRIPTS.get(tone, MOCK_CALL_TRANSCRIPTS["neutral"])
            transcript = _format_template(random.choice(templates), lead)
            duration = random.randint(45, 240)

            interaction = _create_outbound_interaction(lead, "voice", transcript, duration)
            process_interaction(interaction)

            result["status"] = "completed"
            result["interaction_id"] = str(interaction.id)
            result["duration_seconds"] = duration
            result["transcript"] = transcript

        return Response(result, status=drf_status.HTTP_201_CREATED)


class SendEmailView(APIView):
    """Send an email to a lead. In mock mode, generates a simulated reply."""

    def post(self, request, lead_id):
        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return Response({"detail": "Lead not found"}, status=drf_status.HTTP_404_NOT_FOUND)

        _auto_unarchive(lead)

        subject = request.data.get("subject", "").strip()
        body = request.data.get("body", "").strip()
        if not body:
            return Response({"detail": "Email body is required"}, status=drf_status.HTTP_400_BAD_REQUEST)

        email_content = f"Subject: {subject}\n\n{body}" if subject else body

        outbound = _create_outbound_interaction(lead, "email", email_content)
        process_interaction(outbound)

        result = {
            "outbound_id": str(outbound.id),
            "reply": None,
        }

        # In mock mode, simulate a reply
        if getattr(settings, 'COMMS_PROVIDER', 'mock') == 'mock':
            tone = _pick_reply_tone(lead)
            tone_key = "interested" if tone == "positive" else tone
            if tone_key not in MOCK_EMAIL_REPLIES:
                tone_key = "neutral"

            reply_text = _format_template(MOCK_EMAIL_REPLIES[tone_key], lead)
            inbound = _create_inbound_interaction(lead, "email", reply_text)
            process_interaction(inbound)

            result["reply"] = {
                "id": str(inbound.id),
                "message": reply_text,
            }

        return Response(result, status=drf_status.HTTP_201_CREATED)

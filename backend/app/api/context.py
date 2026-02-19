"""
Context API — context pack assembly and provider integration boundary.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from app.models.lead import Lead
from app.services.context_service import assemble_context_pack
from app.providers.voice_provider import VoiceProvider, SMSProvider

voice_provider = VoiceProvider()
sms_provider = SMSProvider()


def _get_lead_or_404(lead_id):
    """Shared lead existence check for context endpoints."""
    if not Lead.objects.filter(id=lead_id).exists():
        return None
    return True


class ContextPackView(APIView):
    """Assemble and return the full context pack for a lead."""

    def get(self, request, lead_id):
        if not _get_lead_or_404(lead_id):
            return Response({"detail": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(assemble_context_pack(lead_id))


class PrepareOutboundCallView(APIView):
    """Context injection boundary for outbound calls."""

    def get(self, request, lead_id):
        if not _get_lead_or_404(lead_id):
            return Response({"detail": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(voice_provider.prepare_outbound_call(lead_id))


class PrepareInboundCallView(APIView):
    """Context injection boundary for inbound calls."""

    def get(self, request, lead_id):
        if not _get_lead_or_404(lead_id):
            return Response({"detail": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(voice_provider.prepare_inbound_call(lead_id))


class PrepareOutboundSMSView(APIView):
    """Context injection boundary for outbound SMS."""

    def get(self, request, lead_id):
        if not _get_lead_or_404(lead_id):
            return Response({"detail": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(sms_provider.prepare_outbound_sms(lead_id))

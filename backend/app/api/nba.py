"""
NBA API — inspect and manage Next Best Action decisions.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from app.models.lead import Lead
from app.models.nba_decision import NBADecision
from app.models.scheduled_action import ScheduledAction
from app.serializers import NBADecisionSerializer, ScheduledActionSerializer
from app.services.nba_engine import compute_nba, persist_nba_decision


class NBACurrentView(APIView):
    """Get the current NBA decision for a lead."""

    def get(self, request, lead_id):
        decision = NBADecision.objects.filter(lead_id=lead_id, is_current=True).first()
        if not decision:
            return Response(None)
        return Response(NBADecisionSerializer(decision).data)


class NBAHistoryView(APIView):
    """Get NBA decision history for a lead."""

    def get(self, request, lead_id):
        limit = min(int(request.query_params.get("limit", 20)), 100)
        decisions = (
            NBADecision.objects
            .filter(lead_id=lead_id)
            .order_by("-created_at")[:limit]
        )
        return Response(NBADecisionSerializer(decisions, many=True).data)


class NBARecomputeView(APIView):
    """Force recompute the NBA for a lead based on current state."""

    def post(self, request, lead_id):
        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return Response({"detail": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)

        result, policy_inputs = compute_nba(lead)
        decision = persist_nba_decision(lead, result, None, policy_inputs)
        return Response(NBADecisionSerializer(decision).data)


class ScheduledActionsView(APIView):
    """Get all pending scheduled actions across all leads."""

    def get(self, request):
        action_status = request.query_params.get("status", "pending")
        limit = min(int(request.query_params.get("limit", 50)), 200)
        actions = (
            ScheduledAction.objects
            .filter(status=action_status)
            .order_by("scheduled_at")[:limit]
        )
        return Response(ScheduledActionSerializer(actions, many=True).data)

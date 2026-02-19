"""
Interaction API — the primary entrypoint for submitting completed interactions.
This triggers the full processing pipeline.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from app.models.lead import Lead
from app.models.interaction import Interaction
from app.serializers import InteractionCreateSerializer, InteractionSerializer
from app.services.interaction_processor import process_interaction


class InteractionSubmitView(APIView):
    """Submit a completed interaction and trigger downstream processing."""

    def post(self, request):
        """
        Submit a completed interaction and trigger downstream processing.

        This is the main entrypoint (Section 2.2 of the spec).
        Submitting an interaction leads to:
        - Updated history/state for the lead
        - LLM-derived signals (summary, facts, intent, sentiment)
        - Updated NBA recommendation with explanation
        - Scheduled future actions (if applicable)
        """
        serializer = InteractionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Validate lead exists
        lead_id = data.pop("lead_id")
        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return Response(
                {"detail": f"Lead {lead_id} not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Create the interaction record
        interaction = Interaction.objects.create(lead=lead, **data)

        # Run the full processing pipeline
        try:
            result = process_interaction(interaction)
        except Exception as e:
            return Response(
                {"detail": f"Processing failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "message": "Interaction processed successfully",
                "interaction_id": str(interaction.id),
                "lead_id": str(lead.id),
                "processing_steps": result["steps"],
            },
            status=status.HTTP_201_CREATED,
        )


class InteractionDetailView(APIView):
    """Get a single interaction with its LLM-derived fields."""

    def get(self, request, interaction_id):
        try:
            interaction = Interaction.objects.get(id=interaction_id)
        except Interaction.DoesNotExist:
            return Response({"detail": "Interaction not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(InteractionSerializer(interaction).data)

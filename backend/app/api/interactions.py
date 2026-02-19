"""
Interaction API — the primary entrypoint for submitting completed interactions.
This triggers the full processing pipeline.

Also provides a batched SMS endpoint that creates individual Interaction
records immediately (for display) and defers LLM extraction until the
thread goes quiet.
"""
import logging
from datetime import datetime, timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from app.models.lead import Lead
from app.models.interaction import Interaction
from app.models.sms_buffer import SMSBuffer
from app.serializers import InteractionCreateSerializer, InteractionSerializer, SMSMessageSerializer
from app.services.interaction_processor import process_interaction
from app.services.sms_batcher import scan_for_urgency, flush_sms_thread

logger = logging.getLogger(__name__)


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


class SMSMessageView(APIView):
    """
    Receive a single SMS message.

    An Interaction record is created immediately so the message appears
    in the chat timeline.  The SMSBuffer row tracks batch state; LLM
    extraction is deferred until the thread goes quiet (or an urgent
    keyword triggers an immediate flush).
    """

    def post(self, request):
        serializer = SMSMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        lead_id = data["lead_id"]
        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return Response(
                {"detail": f"Lead {lead_id} not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        received_at = data.get("received_at") or datetime.now(timezone.utc)
        is_urgent = scan_for_urgency(data["body"])

        interaction = Interaction.objects.create(
            lead=lead,
            channel="sms",
            direction=data["direction"],
            status="completed",
            transcript=data["body"],
            started_at=received_at,
            ended_at=received_at,
        )

        msg = SMSBuffer.objects.create(
            lead=lead,
            direction=data["direction"],
            body=data["body"],
            sender=data.get("sender", ""),
            received_at=received_at,
            is_urgent=is_urgent,
            interaction=interaction,
        )

        if is_urgent:
            try:
                result = flush_sms_thread(lead_id)
                return Response(
                    {
                        "message": "Urgent SMS — thread flushed immediately",
                        "interaction_id": str(interaction.id),
                        "sms_buffer_id": str(msg.id),
                        "lead_id": str(lead.id),
                        "flushed": True,
                        "processing_steps": result["steps"] if result else [],
                    },
                    status=status.HTTP_201_CREATED,
                )
            except Exception as e:
                logger.exception("Urgent SMS flush failed for lead %s", lead_id)
                return Response(
                    {"detail": f"Flush failed: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        # Non-urgent: schedule a background flush check
        try:
            from django_q.tasks import async_task
            async_task(
                "app.services.sms_batcher.check_sms_flush",
                str(lead_id),
                task_name=f"sms_flush_check_{lead_id}",
                q_options={"timeout": 60},
            )
        except Exception:
            logger.warning(
                "django-q not available; flush will rely on periodic sweep "
                "or next urgent message for lead %s", lead_id,
            )

        return Response(
            {
                "message": "SMS buffered — will extract when thread goes quiet",
                "interaction_id": str(interaction.id),
                "sms_buffer_id": str(msg.id),
                "lead_id": str(lead.id),
                "flushed": False,
                "is_urgent": False,
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

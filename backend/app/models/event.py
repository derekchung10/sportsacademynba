import uuid
from django.db import models


class Event(models.Model):
    """
    Append-only event log — the source of truth for what happened.
    Every meaningful state change is recorded as an event.
    This enables full timeline reconstruction and audit trail.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey("Lead", on_delete=models.CASCADE, related_name="events")

    # Event classification
    event_type = models.CharField(max_length=50, db_index=True)
    # Types: interaction_completed, status_changed, nba_produced, context_enriched,
    #        action_scheduled, action_executed, manual_note, channel_preference_updated

    # What triggered this event
    source = models.CharField(max_length=50)  # "system", "agent", "operator", "provider"
    source_id = models.CharField(max_length=36, null=True, blank=True)

    # Event payload (flexible JSON for different event types)
    payload = models.JSONField(default=dict, blank=True)

    # Human-readable description
    description = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "events"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["lead", "-created_at"], name="idx_event_lead_date"),
        ]

    def __str__(self):
        return f"{self.event_type} for lead={self.lead_id} at {self.created_at}"

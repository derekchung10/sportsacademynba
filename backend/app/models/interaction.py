import uuid
from django.db import models


class Interaction(models.Model):
    """
    A completed interaction with a lead — a voice call, SMS exchange, or email.
    This is the primary input that drives the system: when an interaction completes,
    we extract context, update lead state, and produce an NBA decision.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey("Lead", on_delete=models.CASCADE, related_name="interactions")

    # Interaction metadata
    channel = models.CharField(max_length=20)  # "voice", "sms", "email"
    direction = models.CharField(max_length=20)  # "outbound", "inbound"
    status = models.CharField(max_length=30)  # "completed", "no_answer", "voicemail", "failed", "opted_out"

    # Content
    transcript = models.TextField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)

    # LLM-derived fields (populated by processing pipeline)
    summary = models.TextField(null=True, blank=True)
    extracted_facts = models.JSONField(default=list, blank=True)  # List of facts
    detected_intent = models.CharField(max_length=100, null=True, blank=True)
    sentiment = models.CharField(max_length=30, null=True, blank=True)
    open_questions = models.JSONField(default=list, blank=True)  # List of open questions

    # Provider metadata (for traceability)
    provider_call_id = models.CharField(max_length=100, null=True, blank=True)
    agent_id = models.CharField(max_length=100, null=True, blank=True)

    # Timestamps
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Processing state
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "interactions"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["lead", "-created_at"], name="idx_interaction_lead_date"),
        ]

    def __str__(self):
        return f"{self.channel}/{self.direction} ({self.status}) for lead={self.lead_id}"

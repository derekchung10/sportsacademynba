import uuid
from django.db import models


class SMSBuffer(models.Model):
    """
    Staging table for individual SMS messages that tracks batch-processing state.

    Each row is one inbound or outbound SMS.  An Interaction record is created
    immediately (so the message appears in the chat timeline right away).
    Messages accumulate until a flush trigger fires (quiet period, max
    accumulation, message count, or urgent keyword), at which point the LLM
    runs ONCE on the combined thread and the results are applied to the last
    interaction in the batch.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey("Lead", on_delete=models.CASCADE, related_name="sms_buffer")

    direction = models.CharField(max_length=20)  # "inbound" / "outbound"
    body = models.TextField()
    sender = models.CharField(max_length=100, blank=True, default="")

    received_at = models.DateTimeField(help_text="Real-world timestamp of the SMS")

    is_urgent = models.BooleanField(default=False)
    flushed = models.BooleanField(default=False, db_index=True)

    interaction = models.OneToOneField(
        "Interaction", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="sms_buffer_entry",
        help_text="The individual Interaction created for this message (for display)",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sms_buffer"
        ordering = ["received_at"]
        indexes = [
            models.Index(
                fields=["lead", "flushed", "received_at"],
                name="idx_smsbuffer_lead_pending",
            ),
        ]

    def __str__(self):
        tag = "[URGENT] " if self.is_urgent else ""
        return f"{tag}{self.direction} SMS for lead={self.lead_id} @ {self.received_at}"

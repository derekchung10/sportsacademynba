import uuid
from django.db import models


class ScheduledAction(models.Model):
    """
    Represents a future action to be executed at a specific time.
    Linked to an NBA decision that produced the schedule.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey("Lead", on_delete=models.CASCADE, related_name="scheduled_actions")
    nba_decision = models.ForeignKey(
        "NBADecision", on_delete=models.SET_NULL, null=True, blank=True, related_name="scheduled_actions"
    )

    # What to do
    action_type = models.CharField(max_length=50)  # call, sms, email
    channel = models.CharField(max_length=20)
    payload = models.JSONField(default=dict, blank=True)

    # When
    scheduled_at = models.DateTimeField(db_index=True)

    # Execution tracking
    status = models.CharField(max_length=30, default="pending")
    # Statuses: pending, executing, completed, failed, cancelled
    executed_at = models.DateTimeField(null=True, blank=True)
    result = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "scheduled_actions"
        ordering = ["scheduled_at"]
        indexes = [
            models.Index(fields=["status", "scheduled_at"], name="idx_action_status_sched"),
        ]

    def __str__(self):
        return f"{self.action_type} at {self.scheduled_at} ({self.status})"

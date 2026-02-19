import uuid
from django.db import models


class NBADecision(models.Model):
    """
    Next Best Action decision — produced after each interaction completes.

    Design: NBA is deterministic (rule-based policy), not LLM-generated.
    This ensures: same inputs → same outputs, testable, auditable.
    The LLM provides the *context* (summaries, intent); rules provide the *decision*.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey("Lead", on_delete=models.CASCADE, related_name="nba_decisions")
    interaction = models.ForeignKey(
        "Interaction", on_delete=models.SET_NULL, null=True, blank=True, related_name="nba_decisions"
    )

    # The decision
    action = models.CharField(max_length=50)
    # Actions: call, sms, email, wait, schedule_visit, escalate_to_human, no_action
    channel = models.CharField(max_length=20, null=True, blank=True)  # voice, sms, email
    priority = models.CharField(max_length=20, default="normal")  # low, normal, high, urgent

    # Scheduling
    scheduled_for = models.DateTimeField(null=True, blank=True)

    # Reasoning (human-readable explanation of why this action was chosen)
    reasoning = models.TextField()

    # Policy inputs snapshot — what data the rules evaluated (for reproducibility)
    policy_inputs = models.JSONField(default=dict, blank=True)

    # Rule that fired
    rule_name = models.CharField(max_length=100, null=True, blank=True)

    # State
    is_current = models.BooleanField(default=True, db_index=True)
    status = models.CharField(max_length=30, default="pending")
    # Statuses: pending, executing, completed, superseded, cancelled

    created_at = models.DateTimeField(auto_now_add=True)
    executed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "nba_decisions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["lead", "is_current"], name="idx_nba_lead_current"),
        ]

    def __str__(self):
        return f"{self.action}/{self.channel} ({self.priority}) for lead={self.lead_id}"

import uuid
from django.db import models


class NBADecision(models.Model):
    """
    Next Best Action decision — produced by the graph RL engine after each
    interaction completes.

    Strategy comes from Q-learning (which semantic action to take).
    Tactics come from the action brief builder (what to say, tone, prep).
    Same Q-table + same state = same output (deterministic, auditable).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey("Lead", on_delete=models.CASCADE, related_name="nba_decisions")
    interaction = models.ForeignKey(
        "Interaction", on_delete=models.SET_NULL, null=True, blank=True, related_name="nba_decisions"
    )

    # The decision (semantic action name)
    action = models.CharField(max_length=50)
    channel = models.CharField(max_length=20, null=True, blank=True)
    priority = models.CharField(max_length=20, default="normal")

    # Scheduling
    scheduled_for = models.DateTimeField(null=True, blank=True)

    # Reasoning (timing rationale from the action brief)
    reasoning = models.TextField()

    # Policy inputs snapshot (for reproducibility)
    policy_inputs = models.JSONField(default=dict, blank=True)

    # Rule/action identifier (e.g., "rl:scholarship_outreach")
    rule_name = models.CharField(max_length=100, null=True, blank=True)

    # Full action brief: content directives, tone, prep, avoids, message draft
    action_brief = models.JSONField(default=dict, blank=True)

    # Signal context snapshot for outcome tracking
    signal_scores = models.JSONField(default=dict, blank=True)

    # RL state and Q-value that produced this decision
    rl_state = models.CharField(max_length=100, null=True, blank=True)
    rl_q_value = models.FloatField(null=True, blank=True)

    # State
    is_current = models.BooleanField(default=True, db_index=True)
    status = models.CharField(max_length=30, default="pending")

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

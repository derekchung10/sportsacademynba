import uuid
from django.db import models


class StateTransition(models.Model):
    """
    Logs every state transition for the RL engine.
    Enables audit trail, offline policy evaluation, and debugging.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey("Lead", on_delete=models.CASCADE, related_name="state_transitions")
    nba_decision = models.ForeignKey(
        "NBADecision", on_delete=models.SET_NULL, null=True, blank=True, related_name="state_transitions"
    )

    state_before = models.CharField(max_length=100)
    action_taken = models.CharField(max_length=50)
    state_after = models.CharField(max_length=100)
    reward = models.FloatField()

    q_value_before = models.FloatField()
    q_value_after = models.FloatField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "state_transitions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["lead", "-created_at"], name="idx_transition_lead_date"),
        ]

    def __str__(self):
        return f"{self.state_before} --[{self.action_taken}]--> {self.state_after} (r={self.reward:+.2f})"

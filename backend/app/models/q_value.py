import uuid
from django.db import models


class QValue(models.Model):
    """
    Q-table entry for the graph RL engine.
    Stores the learned value of taking a semantic action in a given state.

    State: encoded as "lead_status:context_bucket" (e.g., "interested:financial_concern")
    Action: semantic action name (e.g., "scholarship_outreach")
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    state = models.CharField(max_length=100, db_index=True)
    action = models.CharField(max_length=50)
    q_value = models.FloatField(default=0.0)
    visit_count = models.IntegerField(default=0)
    total_reward = models.FloatField(default=0.0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "q_values"
        unique_together = ("state", "action")
        indexes = [
            models.Index(fields=["state"], name="idx_qvalue_state"),
        ]

    def __str__(self):
        return f"Q({self.state}, {self.action}) = {self.q_value:.4f} (n={self.visit_count})"

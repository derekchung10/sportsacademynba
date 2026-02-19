import uuid
from django.db import models


class ContextArtifact(models.Model):
    """
    Materialized context derived from interactions via LLM processing.
    These are the building blocks assembled into a 'context pack' before calls.

    Design choice: We persist extracted artifacts rather than re-computing them
    each time. This provides:
    - Cost control (LLM called once per interaction, not per context request)
    - Reproducibility (we can trace exactly what context was available at any point)
    - Speed (context assembly is a DB read, not an LLM call)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey("Lead", on_delete=models.CASCADE, related_name="context_artifacts")
    interaction = models.ForeignKey(
        "Interaction", on_delete=models.SET_NULL, null=True, blank=True, related_name="context_artifacts"
    )

    # Artifact type determines how it's used in context assembly
    artifact_type = models.CharField(max_length=50)
    # Core types: summary, extracted_facts, detected_intent, open_questions,
    #             lead_profile_update, conversation_notes
    # Enriched types (Option D): financial_signals, scheduling_constraints,
    #                             family_context, objections

    # The actual content
    content = models.TextField()  # JSON or plain text depending on type

    # Versioning — newer artifacts of same type supersede older ones
    version = models.IntegerField(default=1)
    is_current = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "context_artifacts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["lead", "artifact_type", "is_current"], name="idx_artifact_lead_type_cur"),
            models.Index(fields=["lead", "is_current"], name="idx_artifact_lead_current"),
        ]

    def __str__(self):
        return f"{self.artifact_type} v{self.version} for lead={self.lead_id}"

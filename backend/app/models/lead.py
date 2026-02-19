import uuid
from django.db import models


class Lead(models.Model):
    """
    A Lead represents a parent/guardian that the sports academy wants to contact.
    This is the central entity — all interactions, events, and decisions link to a lead.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Parent/guardian info
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)

    # Child/athlete info
    child_name = models.CharField(max_length=200, null=True, blank=True)
    child_age = models.IntegerField(null=True, blank=True)
    sport = models.CharField(max_length=100, null=True, blank=True)

    # Academy campaign context
    academy_name = models.CharField(max_length=200, null=True, blank=True)
    campaign_goal = models.TextField(null=True, blank=True)

    # Current state (materialized for fast reads; source of truth is the event log)
    status = models.CharField(max_length=50, default="new")
    # Full lifecycle statuses:
    #   Acquisition: new → contacted → interested → trial → enrolled
    #   Retention:   enrolled → active → at_risk → inactive
    #   Terminal:    declined, unresponsive

    preferred_channel = models.CharField(max_length=20, null=True, blank=True)  # voice, sms, email

    total_interactions = models.IntegerField(default=0)
    total_voice_attempts = models.IntegerField(default=0)
    total_sms_attempts = models.IntegerField(default=0)
    total_email_attempts = models.IntegerField(default=0)

    # Tags / notes derived from LLM
    tags = models.JSONField(default=list, blank=True)  # Array of tags

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leads"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.status})"

"""
DRF serializers for API request/response validation.
Separates API contract from DB models.
"""
from rest_framework import serializers
from app.models import Lead, Interaction, Event, ContextArtifact, NBADecision, ScheduledAction


# ─── Lead Serializers ────────────────────────────────────────────────────────

class LeadCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = [
            'first_name', 'last_name', 'phone', 'email',
            'child_name', 'child_age', 'sport',
            'academy_name', 'campaign_goal', 'preferred_channel',
        ]


class LeadUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = [
            'first_name', 'last_name', 'phone', 'email',
            'child_name', 'child_age', 'sport',
            'academy_name', 'campaign_goal', 'status',
            'preferred_channel', 'tags',
        ]
        extra_kwargs = {field: {'required': False} for field in fields}


class LeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = '__all__'


class LeadSummarySerializer(serializers.ModelSerializer):
    """Lightweight lead listing for search/filter results."""
    class Meta:
        model = Lead
        fields = [
            'id', 'first_name', 'last_name', 'phone', 'email',
            'child_name', 'sport', 'status', 'total_interactions',
            'campaign_goal', 'created_at', 'updated_at',
        ]


# ─── Interaction Serializers ─────────────────────────────────────────────────

class InteractionCreateSerializer(serializers.Serializer):
    """Payload to submit a completed interaction."""
    lead_id = serializers.UUIDField()
    channel = serializers.ChoiceField(choices=['voice', 'sms', 'email'])
    direction = serializers.ChoiceField(choices=['outbound', 'inbound'])
    status = serializers.ChoiceField(choices=['completed', 'no_answer', 'voicemail', 'failed', 'opted_out'])
    transcript = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    duration_seconds = serializers.IntegerField(required=False, allow_null=True)
    started_at = serializers.DateTimeField(required=False, allow_null=True)
    ended_at = serializers.DateTimeField(required=False, allow_null=True)
    provider_call_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    agent_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class InteractionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Interaction
        fields = [
            'id', 'lead_id', 'channel', 'direction', 'status',
            'transcript', 'duration_seconds', 'summary', 'extracted_facts',
            'detected_intent', 'sentiment', 'open_questions',
            'started_at', 'ended_at', 'created_at', 'processed',
        ]


# ─── Event Serializers ───────────────────────────────────────────────────────

class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = [
            'id', 'lead_id', 'event_type', 'source', 'source_id',
            'payload', 'description', 'created_at',
        ]


# ─── NBA Decision Serializers ────────────────────────────────────────────────

class NBADecisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = NBADecision
        fields = [
            'id', 'lead_id', 'interaction_id', 'action', 'channel',
            'priority', 'scheduled_for', 'reasoning', 'policy_inputs',
            'rule_name', 'is_current', 'status', 'created_at', 'executed_at',
        ]


# ─── Context Serializers ─────────────────────────────────────────────────────

class ContextArtifactSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContextArtifact
        fields = [
            'id', 'lead_id', 'interaction_id', 'artifact_type',
            'content', 'version', 'is_current', 'created_at',
        ]


# ─── Scheduled Action Serializers ────────────────────────────────────────────

class ScheduledActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduledAction
        fields = [
            'id', 'lead_id', 'nba_decision_id', 'action_type', 'channel',
            'payload', 'scheduled_at', 'status', 'executed_at', 'result',
            'created_at',
        ]



"""
Lead API — CRUD + detail views for the operator dashboard.

Full lifecycle statuses:
  Acquisition: new → contacted → interested → trial → enrolled
  Retention:   enrolled → active → at_risk → inactive
  Terminal:    declined, unresponsive

Category mapping (operator-facing):
- "inbox"          → Non-archived leads with a pending scheduled action (your to-do list)
- "awaiting_reply" → Non-archived, not inbox, not attending
- "attending"      → Enrolled AND actively attending (the healthy ones)
- "archive"        → Manually archived conversations
"""
from django.db.models import Q, Count, Case, When, Value, IntegerField
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

# Full lifecycle order for status sorting (lower = earlier in journey)
STATUS_PIPELINE_ORDER = {
    "new": 0,
    "contacted": 1,
    "interested": 2,
    "trial": 3,
    "enrolled": 4,
    "active": 5,
    "at_risk": 6,
    "inactive": 7,
    "declined": 8,
    "unresponsive": 9,
}

from app.models.lead import Lead
from app.models.interaction import Interaction
from app.models.event import Event
from app.models.context_artifact import ContextArtifact
from app.models.nba_decision import NBADecision
from app.models.scheduled_action import ScheduledAction
from app.serializers import (
    LeadCreateSerializer, LeadUpdateSerializer, LeadSerializer,
    LeadSummarySerializer, InteractionSerializer,
    EventSerializer, NBADecisionSerializer, ContextArtifactSerializer,
    ScheduledActionSerializer,
)


def _inbox_lead_ids():
    """Get IDs of leads that have a pending scheduled action (the operator's inbox)."""
    return set(
        ScheduledAction.objects
        .filter(status="pending")
        .values_list("lead_id", flat=True)
    )


# Statuses that mean "actively attending"
ATTENDING_STATUSES = {"active"}


class LeadListCreateView(APIView):
    """List/search leads and create new leads."""

    def get(self, request):
        """List leads with filtering and search."""
        queryset = Lead.objects.all()

        # ─── Category filter (operator-facing buckets) ─────────────────
        # Priority: attending > inbox > awaiting_reply > archive
        # "Attending" leads (status=active) always go to attending,
        # even if they have a pending scheduled action.
        category = request.query_params.get("category")
        if category == "archive":
            queryset = queryset.filter(is_archived=True)
        elif category == "attending":
            queryset = queryset.filter(status__in=ATTENDING_STATUSES, is_archived=False)
        elif category == "inbox":
            inbox_ids = _inbox_lead_ids()
            queryset = queryset.filter(
                id__in=inbox_ids, is_archived=False
            ).exclude(status__in=ATTENDING_STATUSES)
        elif category == "awaiting_reply":
            inbox_ids = _inbox_lead_ids()
            queryset = queryset.filter(is_archived=False).exclude(
                status__in=ATTENDING_STATUSES
            ).exclude(id__in=inbox_ids)

        # ─── Status filter (still available for power users) ───────────
        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        sport = request.query_params.get("sport")
        if sport:
            queryset = queryset.filter(sport__icontains=sport)

        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(phone__icontains=search) |
                Q(email__icontains=search) |
                Q(child_name__icontains=search)
            )

        # ─── Always annotate NBA priority for display ────────────────
        from django.db.models import Subquery, OuterRef
        priority_sq = (
            NBADecision.objects
            .filter(lead_id=OuterRef("id"), is_current=True)
            .values("priority")[:1]
        )
        queryset = queryset.annotate(nba_priority=Subquery(priority_sq))

        # ─── Sorting ──────────────────────────────────────────────────
        sort_by = request.query_params.get("sort_by", "updated_at")
        sort_order = request.query_params.get("sort_order", "desc")
        allowed_sort_fields = [
            "first_name", "last_name", "status", "created_at",
            "updated_at", "total_interactions", "nba_priority",
        ]
        if sort_by not in allowed_sort_fields:
            sort_by = "updated_at"

        # Reusable priority rank annotation for tiebreaking
        priority_ordering = Case(
            When(nba_priority="urgent", then=Value(0)),
            When(nba_priority="high", then=Value(1)),
            When(nba_priority="normal", then=Value(2)),
            When(nba_priority="low", then=Value(3)),
            default=Value(99),
            output_field=IntegerField(),
        )
        queryset = queryset.annotate(priority_rank=priority_ordering)

        if sort_by == "nba_priority":
            queryset = queryset.order_by("priority_rank", "-updated_at")
        elif sort_by == "status":
            status_ordering = Case(
                *[When(status=s, then=Value(idx)) for s, idx in STATUS_PIPELINE_ORDER.items()],
                default=Value(99),
                output_field=IntegerField(),
            )
            order_prefix = "-" if sort_order == "desc" else ""
            queryset = queryset.annotate(status_order=status_ordering).order_by(
                f"{order_prefix}status_order"
            )
        elif sort_by == "updated_at":
            order_prefix = "-" if sort_order == "desc" else ""
            queryset = queryset.order_by(f"{order_prefix}updated_at", "priority_rank")
        else:
            order_prefix = "-" if sort_order == "desc" else ""
            queryset = queryset.order_by(f"{order_prefix}{sort_by}")

        # ─── Pagination ──────────────────────────────────────────────
        limit = min(int(request.query_params.get("limit", 50)), 200)
        offset = int(request.query_params.get("offset", 0))
        queryset = queryset[offset:offset + limit]

        serializer = LeadSummarySerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Create a new lead."""
        serializer = LeadCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        lead = Lead.objects.create(**serializer.validated_data)

        # Log creation event
        Event.objects.create(
            lead_id=lead.id,
            event_type="lead_created",
            source="operator",
            description=f"Lead created: {lead.first_name} {lead.last_name}",
        )

        return Response(LeadSerializer(lead).data, status=status.HTTP_201_CREATED)


class LeadStatsView(APIView):
    """Get aggregate stats for the dashboard."""

    def get(self, request):
        # Status counts (for detail breakdowns if needed)
        status_counts = (
            Lead.objects
            .values("status")
            .annotate(count=Count("id"))
            .order_by()
        )
        by_status = {row["status"]: row["count"] for row in status_counts}
        total = sum(by_status.values())

        # Category counts — each lead goes into exactly one bucket
        inbox_ids = _inbox_lead_ids()
        active_leads = Lead.objects.filter(is_archived=False)

        attending_count = active_leads.filter(
            status__in=ATTENDING_STATUSES
        ).count()
        inbox_count = active_leads.filter(
            id__in=inbox_ids
        ).exclude(status__in=ATTENDING_STATUSES).count()
        archive_count = Lead.objects.filter(is_archived=True).count()
        awaiting_reply_count = (
            active_leads
            .exclude(id__in=inbox_ids)
            .exclude(status__in=ATTENDING_STATUSES)
            .count()
        )

        pending_actions = ScheduledAction.objects.filter(status="pending").count()

        return Response({
            "total_leads": total,
            "leads_by_status": by_status,
            "leads_by_category": {
                "inbox": inbox_count,
                "awaiting_reply": awaiting_reply_count,
                "attending": attending_count,
                "archive": archive_count,
            },
            "pending_scheduled_actions": pending_actions,
        })


class LeadDetailView(APIView):
    """Full lead detail and update."""

    def get(self, request, lead_id):
        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return Response({"detail": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)

        interactions = Interaction.objects.filter(lead_id=lead_id).order_by("-created_at")
        events = Event.objects.filter(lead_id=lead_id).order_by("-created_at")
        current_nba = NBADecision.objects.filter(lead_id=lead_id, is_current=True).first()
        context_artifacts = ContextArtifact.objects.filter(lead_id=lead_id, is_current=True)
        scheduled_actions = ScheduledAction.objects.filter(lead_id=lead_id).order_by("-scheduled_at")

        data = {
            "lead": LeadSerializer(lead).data,
            "interactions": InteractionSerializer(interactions, many=True).data,
            "events": EventSerializer(events, many=True).data,
            "current_nba": NBADecisionSerializer(current_nba).data if current_nba else None,
            "context_artifacts": ContextArtifactSerializer(context_artifacts, many=True).data,
            "scheduled_actions": ScheduledActionSerializer(scheduled_actions, many=True).data,
        }
        return Response(data)

    def delete(self, request, lead_id):
        """Archive a lead (soft-delete). Use PATCH with is_archived=false to unarchive."""
        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return Response({"detail": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)

        lead.is_archived = True
        lead.save(update_fields=["is_archived", "updated_at"])

        Event.objects.create(
            lead_id=lead.id,
            event_type="lead_archived",
            source="operator",
            description=f"Conversation archived",
        )

        return Response({"detail": "Archived", "lead_id": str(lead.id)})

    def patch(self, request, lead_id):
        """Update a lead's info. Logs contact changes as events."""
        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return Response({"detail": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)

        # Snapshot fields we want to track changes for
        tracked_fields = {"phone", "email"}
        old_values = {f: getattr(lead, f) for f in tracked_fields}

        serializer = LeadUpdateSerializer(lead, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Log events for any contact-info changes
        for field in tracked_fields:
            old_val = old_values[field] or ""
            new_val = getattr(lead, field) or ""
            if old_val != new_val:
                label = "Phone" if field == "phone" else "Email"
                desc = f"{label} updated"
                if old_val:
                    desc += f": {old_val} → {new_val}" if new_val else f": {old_val} removed"
                else:
                    desc += f": {new_val}"

                Event.objects.create(
                    lead_id=lead.id,
                    event_type="contact_updated",
                    source="operator",
                    payload={"field": field, "old_value": old_val, "new_value": new_val},
                    description=desc,
                )

        return Response(LeadSerializer(lead).data)

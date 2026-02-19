"""
App URL configuration — maps to the same API structure as the original FastAPI app.
"""
from django.urls import path
from app.api import leads, interactions, context, nba, communicate

urlpatterns = [
    # Leads
    path('leads/', leads.LeadListCreateView.as_view()),
    path('leads/stats', leads.LeadStatsView.as_view()),
    path('leads/<uuid:lead_id>', leads.LeadDetailView.as_view()),

    # Interactions
    path('interactions/', interactions.InteractionSubmitView.as_view()),
    path('interactions/sms', interactions.SMSMessageView.as_view()),
    path('interactions/<uuid:interaction_id>', interactions.InteractionDetailView.as_view()),

    # Communication (operator-initiated outreach)
    path('communicate/<uuid:lead_id>/sms', communicate.SendSMSView.as_view()),
    path('communicate/<uuid:lead_id>/call', communicate.MakeCallView.as_view()),
    path('communicate/<uuid:lead_id>/email', communicate.SendEmailView.as_view()),

    # Context
    path('context/<uuid:lead_id>/pack', context.ContextPackView.as_view()),
    path('context/<uuid:lead_id>/prepare-outbound-call', context.PrepareOutboundCallView.as_view()),
    path('context/<uuid:lead_id>/prepare-inbound-call', context.PrepareInboundCallView.as_view()),
    path('context/<uuid:lead_id>/prepare-outbound-sms', context.PrepareOutboundSMSView.as_view()),

    # NBA
    path('nba/<uuid:lead_id>/current', nba.NBACurrentView.as_view()),
    path('nba/<uuid:lead_id>/history', nba.NBAHistoryView.as_view()),
    path('nba/<uuid:lead_id>/recompute', nba.NBARecomputeView.as_view()),
    path('nba/scheduled-actions', nba.ScheduledActionsView.as_view()),
]

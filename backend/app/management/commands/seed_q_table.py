"""
Seed the Q-table with initial values derived from the original rule engine's
priority ordering. This gives the RL engine a warm start so day-1 behavior
is at least as good as the hand-crafted rules.

Usage:
    python manage.py seed_q_table
    python manage.py seed_q_table --reset  # Clear and re-seed
"""
from django.core.management.base import BaseCommand

from app.models.q_value import QValue


# Initial Q-values: (state, action) -> q_value
# Derived from the original rule engine's priority ordering and domain knowledge.
# Higher values = stronger prior belief that this action works in this state.
INITIAL_Q_VALUES = {
    # ─── New leads ────────────────────────────────────────────────────
    ("new:neutral", "warm_follow_up"): 0.5,
    ("new:neutral", "info_send"): 0.3,
    ("new:neutral", "gentle_nudge"): 0.2,

    # ─── Contacted leads ─────────────────────────────────────────────
    ("contacted:positive_engagement", "scheduling_push"): 0.7,
    ("contacted:positive_engagement", "warm_follow_up"): 0.5,
    ("contacted:neutral", "warm_follow_up"): 0.4,
    ("contacted:neutral", "gentle_nudge"): 0.3,
    ("contacted:unreached", "channel_switch"): 0.4,
    ("contacted:unreached", "gentle_nudge"): 0.3,
    ("contacted:considering", "gentle_nudge"): 0.4,
    ("contacted:considering", "info_send"): 0.3,
    ("contacted:financial_concern", "scholarship_outreach"): 0.5,
    ("contacted:has_objections", "objection_address"): 0.5,
    ("contacted:negative", "wait"): 0.4,
    ("contacted:negative", "gentle_nudge"): 0.2,
    ("contacted:scheduling_intent", "scheduling_push"): 0.8,
    ("contacted:family_context", "family_engage"): 0.4,

    # ─── Interested leads ────────────────────────────────────────────
    ("interested:positive_engagement", "scheduling_push"): 0.8,
    ("interested:positive_engagement", "warm_follow_up"): 0.5,
    ("interested:financial_concern", "scholarship_outreach"): 0.6,
    ("interested:financial_concern", "warm_follow_up"): 0.3,
    ("interested:has_objections", "objection_address"): 0.5,
    ("interested:has_objections", "warm_follow_up"): 0.3,
    ("interested:considering", "gentle_nudge"): 0.4,
    ("interested:considering", "warm_follow_up"): 0.3,
    ("interested:scheduling_intent", "scheduling_push"): 0.9,
    ("interested:neutral", "warm_follow_up"): 0.5,
    ("interested:neutral", "scheduling_push"): 0.4,
    ("interested:unreached", "channel_switch"): 0.4,
    ("interested:unreached", "gentle_nudge"): 0.3,
    ("interested:family_context", "family_engage"): 0.5,
    ("interested:family_context", "warm_follow_up"): 0.3,
    ("interested:negative", "wait"): 0.4,
    ("interested:novel_signal", "warm_follow_up"): 0.4,

    # ─── Trial leads ─────────────────────────────────────────────────
    ("trial:positive_engagement", "scheduling_push"): 0.7,
    ("trial:positive_engagement", "warm_follow_up"): 0.5,
    ("trial:neutral", "warm_follow_up"): 0.5,
    ("trial:neutral", "gentle_nudge"): 0.3,
    ("trial:financial_concern", "scholarship_outreach"): 0.5,
    ("trial:has_objections", "objection_address"): 0.4,
    ("trial:negative", "wait"): 0.4,
    ("trial:unreached", "gentle_nudge"): 0.3,

    # ─── Enrolled leads ──────────────────────────────────────────────
    ("enrolled:neutral", "welcome_onboard"): 0.7,
    ("enrolled:positive_engagement", "welcome_onboard"): 0.8,
    ("enrolled:financial_concern", "scholarship_outreach"): 0.4,

    # ─── Active leads (retention) ────────────────────────────────────
    ("active:neutral", "retention_check_in"): 0.4,
    ("active:neutral", "wait"): 0.3,
    ("active:positive_engagement", "retention_check_in"): 0.5,
    ("active:negative", "retention_check_in"): 0.5,
    ("active:has_objections", "objection_address"): 0.4,

    # ─── At-risk leads ───────────────────────────────────────────────
    ("at_risk:neutral", "retention_check_in"): 0.6,
    ("at_risk:neutral", "warm_follow_up"): 0.4,
    ("at_risk:negative", "retention_check_in"): 0.5,
    ("at_risk:negative", "gentle_nudge"): 0.3,
    ("at_risk:financial_concern", "scholarship_outreach"): 0.5,
    ("at_risk:has_objections", "objection_address"): 0.5,
    ("at_risk:unreached", "channel_switch"): 0.4,
    ("at_risk:family_context", "family_engage"): 0.4,

    # ─── Inactive leads ──────────────────────────────────────────────
    ("inactive:neutral", "gentle_nudge"): 0.4,
    ("inactive:neutral", "wait"): 0.3,
    ("inactive:positive_engagement", "warm_follow_up"): 0.5,
    ("inactive:unreached", "channel_switch"): 0.3,
    ("inactive:negative", "wait"): 0.5,
    ("inactive:negative", "stop"): 0.3,
    ("inactive:financial_concern", "scholarship_outreach"): 0.4,
}


class Command(BaseCommand):
    help = "Seed the Q-table with initial values from domain knowledge"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Clear all existing Q-values before seeding",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            deleted, _ = QValue.objects.all().delete()
            self.stdout.write(f"Cleared {deleted} existing Q-values.")

        created = 0
        skipped = 0
        for (state, action), q_val in INITIAL_Q_VALUES.items():
            _, was_created = QValue.objects.get_or_create(
                state=state, action=action,
                defaults={"q_value": q_val, "visit_count": 0, "total_reward": 0.0},
            )
            if was_created:
                created += 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seeded Q-table: {created} created, {skipped} already existed. "
            f"Total entries: {QValue.objects.count()}"
        ))

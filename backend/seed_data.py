"""
Seed data script — populates the database with realistic demo data
covering the full family lifecycle (acquisition + retention).

Usage: cd backend && python seed_data.py
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'academy_outreach.settings')
django.setup()

from app.models.lead import Lead
from app.models.interaction import Interaction
from app.services.interaction_processor import process_interaction


LEADS = [
    # ─── Acquisition funnel ─────────────────────────────────────────
    {
        "first_name": "Priya",
        "last_name": "Patel",
        "phone": "+1-555-0105",
        "email": "priya.patel@example.com",
        "child_name": "Arjun Patel",
        "child_age": 13,
        "sport": "Track & Field",
        "academy_name": "Elite Sports Academy",
        "campaign_goal": "New family — saw ad on community board",
        "preferred_channel": "sms",
    },
    {
        "first_name": "David",
        "last_name": "Chen",
        "phone": "+1-555-0102",
        "email": "david.chen@example.com",
        "child_name": "Lily Chen",
        "child_age": 12,
        "sport": "Tennis",
        "academy_name": "Elite Sports Academy",
        "campaign_goal": "Interested in tennis — came from school flyer",
        "preferred_channel": "sms",
    },
    {
        "first_name": "James",
        "last_name": "Thompson",
        "phone": "+1-555-0104",
        "email": None,
        "child_name": "Emma Thompson",
        "child_age": 11,
        "sport": "Swimming",
        "academy_name": "Elite Sports Academy",
        "campaign_goal": "Friend referred — interested in swim team",
    },
    {
        "first_name": "Sarah",
        "last_name": "Mitchell",
        "phone": "+1-555-0101",
        "email": "sarah.mitchell@example.com",
        "child_name": "Jake Mitchell",
        "child_age": 14,
        "sport": "Basketball",
        "academy_name": "Elite Sports Academy",
        "campaign_goal": "Visited for trial — deciding on enrollment",
        "preferred_channel": "voice",
    },

    # ─── Retention (already enrolled / active) ──────────────────────
    {
        "first_name": "Maria",
        "last_name": "Rodriguez",
        "phone": "+1-555-0103",
        "email": "maria.rodriguez@example.com",
        "child_name": "Carlos Rodriguez",
        "child_age": 16,
        "sport": "Soccer",
        "academy_name": "Elite Sports Academy",
        "campaign_goal": "Enrolled — attending twice a week",
        "preferred_channel": "voice",
        "status": "active",
    },
    {
        "first_name": "Robert",
        "last_name": "Williams",
        "phone": "+1-555-0106",
        "email": "r.williams@example.com",
        "child_name": "Tyler Williams",
        "child_age": 15,
        "sport": "Basketball",
        "academy_name": "Elite Sports Academy",
        "campaign_goal": "Enrolled — been attending since September",
        "preferred_channel": "voice",
        "status": "active",
    },
    {
        "first_name": "Angela",
        "last_name": "Kim",
        "phone": "+1-555-0107",
        "email": "angela.kim@example.com",
        "child_name": "Sophie Kim",
        "child_age": 10,
        "sport": "Gymnastics",
        "academy_name": "Elite Sports Academy",
        "campaign_goal": "Enrolled — missed last 2 classes",
        "preferred_channel": "sms",
        "status": "at_risk",
    },
    {
        "first_name": "Marcus",
        "last_name": "Brown",
        "phone": "+1-555-0108",
        "email": "m.brown@example.com",
        "child_name": "Jaylen Brown",
        "child_age": 13,
        "sport": "Basketball",
        "academy_name": "Elite Sports Academy",
        "campaign_goal": "Was active — hasn't come in over a month",
        "preferred_channel": "voice",
        "status": "inactive",
    },
    {
        "first_name": "Lisa",
        "last_name": "Nguyen",
        "phone": "+1-555-0109",
        "email": "lisa.nguyen@example.com",
        "child_name": "Ethan Nguyen",
        "child_age": 9,
        "sport": "Soccer",
        "academy_name": "Elite Sports Academy",
        "campaign_goal": "Just enrolled — hasn't started classes yet",
        "preferred_channel": "sms",
        "status": "enrolled",
    },
    {
        "first_name": "Tom",
        "last_name": "Garcia",
        "phone": "+1-555-0110",
        "email": "tom.garcia@example.com",
        "child_name": "Mia Garcia",
        "child_age": 14,
        "sport": "Tennis",
        "academy_name": "Elite Sports Academy",
        "campaign_goal": "Contacted — decided to go elsewhere",
        "status": "declined",
    },
]

# Interactions to simulate a realistic timeline
INTERACTIONS = [
    # ─── David Chen (contacted): SMS conversation, on the fence ─────
    {
        "lead_index": 1,
        "channel": "sms",
        "direction": "outbound",
        "status": "completed",
        "transcript": (
            "Agent: Hi David, this is Elite Sports Academy. We have an excellent tennis program "
            "that would be perfect for Lily. Would you be interested in scheduling a visit?\n"
            "David: Hi, thanks for reaching out. Lily does play tennis but she's already "
            "at another academy. What makes your program different?\n"
            "Agent: Great question! Our coaches include two former ATP tour players, and we "
            "have a 4:1 student-to-coach ratio. We also offer college recruitment support. "
            "Would you like to come see a practice session?\n"
            "David: Hmm, let me think about it. The coach ratio is impressive though."
        ),
    },

    # ─── James Thompson (interested): Hard to reach but interested ──
    {
        "lead_index": 2,
        "channel": "voice",
        "direction": "outbound",
        "status": "no_answer",
        "duration_seconds": 0,
    },
    {
        "lead_index": 2,
        "channel": "voice",
        "direction": "outbound",
        "status": "voicemail",
        "duration_seconds": 30,
        "transcript": (
            "Agent: Hi James, this is Elite Sports Academy calling about our competitive "
            "swim team for Emma. We have some exciting programs for her age group. "
            "Please call us back at 555-0200 or reply to our text. Thanks!"
        ),
    },
    {
        "lead_index": 2,
        "channel": "sms",
        "direction": "inbound",
        "status": "completed",
        "transcript": (
            "James: Sorry I missed your calls! Emma is really interested in swimming. "
            "Can we come watch a practice session this week?"
        ),
    },

    # ─── Sarah Mitchell (trial): Came for trial, deciding ──────────
    {
        "lead_index": 3,
        "channel": "voice",
        "direction": "outbound",
        "status": "completed",
        "duration_seconds": 180,
        "transcript": (
            "Agent: Hi Sarah, this is Coach Davis from Elite Sports Academy. "
            "I'm calling about our basketball program for Jake.\n"
            "Sarah: Oh yes! Jake came to the trial session last Saturday and loved it. "
            "He's been talking about it nonstop.\n"
            "Agent: That's wonderful! Jake did great — the coaches were impressed. "
            "Are you thinking about enrolling him for the full session?\n"
            "Sarah: We definitely want to, but we're trying to figure out the schedule "
            "with his other activities. How much is it?\n"
            "Agent: The program is $200/month, twice a week. And we offer 10% off "
            "if you register this week. We also have flexible scheduling.\n"
            "Sarah: Let me talk to my husband tonight and I'll get back to you."
        ),
    },

    # ─── Maria Rodriguez (active): Check-in conversation ────────────
    {
        "lead_index": 4,
        "channel": "sms",
        "direction": "outbound",
        "status": "completed",
        "transcript": (
            "Agent: Hi Maria! Just wanted to check in — how's Carlos enjoying soccer this season?\n"
            "Maria: He loves it! Coach says he's one of the hardest workers on the team.\n"
            "Agent: That's great to hear! We have a tournament coming up March 15th. "
            "Carlos is definitely on the roster if you're interested.\n"
            "Maria: Absolutely! He'd love that. Can you send me the details?"
        ),
    },

    # ─── Angela Kim (at_risk): Missing classes ──────────────────────
    {
        "lead_index": 6,
        "channel": "sms",
        "direction": "outbound",
        "status": "completed",
        "transcript": (
            "Agent: Hi Angela! We noticed Sophie missed the last couple gymnastics classes. "
            "Is everything okay? We'd love to see her back!\n"
            "Angela: Hi, thanks for checking. Sophie's been dealing with a cold. "
            "Also, the Tuesday class conflicts with her piano lessons now.\n"
            "Agent: Oh no, hope she feels better! We actually have a Thursday class at the same time "
            "— would that work better?\n"
            "Angela: Thursday could work! Let me check and get back to you."
        ),
    },

    # ─── Marcus Brown (inactive): Dropped off, trying to win back ───
    {
        "lead_index": 7,
        "channel": "voice",
        "direction": "outbound",
        "status": "completed",
        "duration_seconds": 120,
        "transcript": (
            "Agent: Hi Marcus, this is Elite Sports Academy. We haven't seen Jaylen "
            "at basketball in a while and wanted to check in.\n"
            "Marcus: Hey, yeah... Jaylen kind of lost motivation. His grades slipped "
            "and we had to prioritize school.\n"
            "Agent: I completely understand — school comes first. You know, we actually have "
            "a tutoring partnership now where kids can get homework help before practice. "
            "Might help with the balance.\n"
            "Marcus: Really? I didn't know about that. That could actually help. "
            "Let me talk to Jaylen about it.\n"
            "Agent: Take your time. We'd love to have him back whenever he's ready."
        ),
    },

    # ─── Tom Garcia (declined): Said no ─────────────────────────────
    {
        "lead_index": 9,
        "channel": "voice",
        "direction": "outbound",
        "status": "completed",
        "duration_seconds": 90,
        "transcript": (
            "Agent: Hi Tom, this is Elite Sports Academy calling about our tennis program for Mia.\n"
            "Tom: Thanks for calling, but we actually signed Mia up at the community center "
            "down the street. It's closer and cheaper.\n"
            "Agent: No problem at all! If anything changes or Mia wants to try a more "
            "competitive program, we'd love to have her.\n"
            "Tom: Appreciate that. I'll keep it in mind."
        ),
    },
]


def seed():
    # Check if already seeded
    existing = Lead.objects.count()
    if existing > 0:
        print(f"Database already has {existing} leads. Skipping seed.")
        print("Run 'python manage.py flush --no-input' to clear, then re-seed.")
        return

    # Create leads
    lead_records = []
    for lead_data in LEADS:
        lead = Lead.objects.create(**lead_data)
        lead_records.append(lead)

    print(f"Created {len(lead_records)} leads")

    # Create and process interactions
    for i, interaction_data in enumerate(INTERACTIONS):
        data = dict(interaction_data)
        lead_idx = data.pop("lead_index")
        lead = lead_records[lead_idx]

        interaction = Interaction.objects.create(lead=lead, **data)

        result = process_interaction(interaction)
        lead.refresh_from_db()
        print(
            f"  [{i+1}/{len(INTERACTIONS)}] {lead.first_name} {lead.last_name} ({lead.status}): "
            f"{interaction.channel}/{interaction.direction}/{interaction.status}"
        )

    # Force-set intended statuses for retention families
    # (interactions may have overridden them via the processing pipeline)
    STATUS_OVERRIDES = {
        4: "active",       # Maria — actively attending
        5: "active",       # Robert — actively attending
        6: "at_risk",      # Angela — missing classes
        7: "inactive",     # Marcus — hasn't come in a month
        8: "enrolled",     # Lisa — just enrolled, hasn't started
        9: "declined",     # Tom — chose another program
    }
    for idx, target_status in STATUS_OVERRIDES.items():
        lead = lead_records[idx]
        lead.refresh_from_db()
        if lead.status != target_status:
            old = lead.status
            lead.status = target_status
            lead.save()
            print(f"  Status override: {lead.first_name} {old} -> {target_status}")

    # Trigger NBA for all leads to get current recommendations
    from app.services.nba_engine import compute_nba, persist_nba_decision
    for lead in lead_records:
        lead.refresh_from_db()
        result, inputs = compute_nba(lead)
        persist_nba_decision(lead, result, None, inputs)
        print(f"  NBA for {lead.first_name} ({lead.status}): {result.action}/{result.channel}")

    # Print summary by status
    print(f"\n{'='*50}")
    print(f"Seed complete! {len(lead_records)} families across the lifecycle:\n")
    for lead in lead_records:
        lead.refresh_from_db()
        print(f"  {lead.first_name} {lead.last_name:12s} | {lead.status:12s} | {lead.child_name} ({lead.sport})")
    print(f"\nRun the server: python manage.py runserver")
    print(f"Open dashboard: http://localhost:5173/")


if __name__ == "__main__":
    seed()

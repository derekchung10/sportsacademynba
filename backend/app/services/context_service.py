"""
Context Enrichment & Injection Service

Responsibilities:
1. After an interaction: persist LLM-derived artifacts (enrichment)
2. Before a call: assemble a "context pack" from stored artifacts (injection)

Design decision: Context packs are assembled on-demand from persisted artifacts.
We DON'T persist the assembled pack because it would go stale. Instead, we persist
the ingredients (artifacts) and assemble fresh each time.

Enriched dimensions (Option D):
- financial_signals: cost concerns, scholarship interest, budget signals
- scheduling_constraints: time/day constraints, preferred windows
- family_context: siblings, decision-maker dynamics, household notes
- objections: specific concerns with severity tracking
"""
import json
import logging

from app.models.lead import Lead
from app.models.interaction import Interaction
from app.models.context_artifact import ContextArtifact
from app.models.nba_decision import NBADecision
from app.services.llm_service import LLMExtractionResult
from app.utils import build_child_info, utcnow

logger = logging.getLogger(__name__)


def enrich_from_extraction(lead_id, interaction_id, extraction: LLMExtractionResult) -> list:
    """
    Persist LLM extraction results as context artifacts.
    Marks previous artifacts of the same type as non-current.
    Includes enriched context dimensions (financial, scheduling, family, objections).
    """
    artifacts = []

    # ─── Core artifacts (original) ─────────────────────────────────────

    # Summary artifact
    if extraction.summary:
        artifact = _create_artifact(lead_id, interaction_id, "summary", extraction.summary)
        artifacts.append(artifact)

    # Extracted facts — append to existing facts rather than replace
    if extraction.facts:
        artifact = _create_artifact(
            lead_id, interaction_id, "extracted_facts",
            json.dumps(extraction.facts)
        )
        artifacts.append(artifact)

    # Detected intent
    if extraction.intent:
        artifact = _create_artifact(lead_id, interaction_id, "detected_intent", extraction.intent)
        artifacts.append(artifact)

    # Open questions
    if extraction.open_questions:
        artifact = _create_artifact(
            lead_id, interaction_id, "open_questions",
            json.dumps(extraction.open_questions)
        )
        artifacts.append(artifact)

    # ─── Enriched context dimensions (Option D) ────────────────────────

    # Financial signals — only store if there's a real signal
    if extraction.financial_signals and extraction.financial_signals.get("concern_level", "none") != "none":
        artifact = _create_artifact(
            lead_id, interaction_id, "financial_signals",
            json.dumps(extraction.financial_signals)
        )
        artifacts.append(artifact)

    # Scheduling constraints — only store if non-empty
    if extraction.scheduling_constraints and (
        extraction.scheduling_constraints.get("constraints")
        or extraction.scheduling_constraints.get("preferred_times")
    ):
        artifact = _create_artifact(
            lead_id, interaction_id, "scheduling_constraints",
            json.dumps(extraction.scheduling_constraints)
        )
        artifacts.append(artifact)

    # Family context — only store if non-empty
    if extraction.family_context and (
        extraction.family_context.get("siblings")
        or extraction.family_context.get("decision_makers")
        or extraction.family_context.get("notes")
    ):
        artifact = _create_artifact(
            lead_id, interaction_id, "family_context",
            json.dumps(extraction.family_context)
        )
        artifacts.append(artifact)

    # Objections — only store if there are actual objections
    if extraction.objections:
        artifact = _create_artifact(
            lead_id, interaction_id, "objections",
            json.dumps(extraction.objections)
        )
        artifacts.append(artifact)

    return artifacts


def _create_artifact(lead_id, interaction_id, artifact_type: str, content: str) -> ContextArtifact:
    """Create a new artifact and mark previous ones of this type as non-current."""
    # Get current version number
    existing = (
        ContextArtifact.objects
        .filter(lead_id=lead_id, artifact_type=artifact_type, is_current=True)
        .first()
    )
    new_version = (existing.version + 1) if existing else 1

    if existing:
        existing.is_current = False
        existing.save(update_fields=["is_current"])

    artifact = ContextArtifact.objects.create(
        lead_id=lead_id,
        interaction_id=interaction_id,
        artifact_type=artifact_type,
        content=content,
        version=new_version,
        is_current=True,
    )
    return artifact


def assemble_context_pack(lead_id) -> dict:
    """
    Assemble a context pack for an outbound/inbound call.
    This is the "injection boundary" — what gets loaded before a call starts.

    Pulls from:
    - Lead record (basic info, campaign goal, status)
    - Current context artifacts (summaries, facts, intents, enriched dimensions)
    - Recent interactions (last 5)
    - Current NBA decision
    """
    lead = Lead.objects.filter(id=lead_id).first()
    if not lead:
        raise ValueError(f"Lead {lead_id} not found")

    # Get current artifacts
    current_artifacts = ContextArtifact.objects.filter(lead_id=lead_id, is_current=True)

    # Organize by type
    artifacts_by_type = {}
    for a in current_artifacts:
        artifacts_by_type[a.artifact_type] = a.content

    # Get latest summary
    latest_summary = artifacts_by_type.get("summary")

    # Collect all facts (from all interactions, not just current)
    all_fact_artifacts = (
        ContextArtifact.objects
        .filter(lead_id=lead_id, artifact_type="extracted_facts")
        .order_by("created_at")
    )
    known_facts = []
    for fa in all_fact_artifacts:
        try:
            facts = json.loads(fa.content)
            known_facts.extend(facts)
        except (json.JSONDecodeError, TypeError):
            known_facts.append(fa.content)
    # Deduplicate
    known_facts = list(dict.fromkeys(known_facts))

    # Intents
    detected_intents = list(
        ContextArtifact.objects
        .filter(lead_id=lead_id, artifact_type="detected_intent")
        .order_by("-created_at")[:3]
        .values_list("content", flat=True)
    )

    # Open questions
    open_questions = []
    oq = artifacts_by_type.get("open_questions")
    if oq:
        try:
            open_questions = json.loads(oq)
        except (json.JSONDecodeError, TypeError):
            open_questions = [oq]

    # ─── Enriched dimensions (accumulated across interactions) ─────────

    # Financial signals — merge across all interactions, keep highest concern level
    financial_signals = _accumulate_financial_signals(lead_id)

    # Scheduling constraints — merge all constraints and preferred times
    scheduling_constraints = _accumulate_scheduling_constraints(lead_id)

    # Family context — merge siblings, decision-makers, notes
    family_context = _accumulate_family_context(lead_id)

    # Objections — collect all, deduplicate by topic, keep highest severity
    objections = _accumulate_objections(lead_id)

    # Recent interactions
    recent_interactions = (
        Interaction.objects
        .filter(lead_id=lead_id)
        .order_by("-created_at")[:5]
    )
    recent_list = [
        {
            "id": str(i.id),
            "channel": i.channel,
            "direction": i.direction,
            "status": i.status,
            "summary": i.summary,
            "detected_intent": i.detected_intent,
            "sentiment": i.sentiment,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        }
        for i in recent_interactions
    ]

    # Current NBA
    current_nba = (
        NBADecision.objects
        .filter(lead_id=lead_id, is_current=True)
        .first()
    )
    nba_dict = None
    if current_nba:
        nba_dict = {
            "action": current_nba.action,
            "channel": current_nba.channel,
            "priority": current_nba.priority,
            "reasoning": current_nba.reasoning,
            "scheduled_for": current_nba.scheduled_for.isoformat() if current_nba.scheduled_for else None,
        }

    return {
        "lead_id": str(lead.id),
        "lead_name": f"{lead.first_name} {lead.last_name}",
        "child_info": build_child_info(lead) or None,
        "campaign_goal": lead.campaign_goal,
        "current_status": lead.status,
        "interaction_count": lead.total_interactions,
        "latest_summary": latest_summary,
        "known_facts": known_facts,
        "detected_intents": detected_intents,
        "open_questions": open_questions,
        # Enriched context dimensions
        "financial_signals": financial_signals,
        "scheduling_constraints": scheduling_constraints,
        "family_context": family_context,
        "objections": objections,
        "recent_interactions": recent_list,
        "current_nba": nba_dict,
        "assembled_at": utcnow().isoformat(),
    }


# ─── Accumulation helpers ───────────────────────────────────────────────────
# These merge context across all interactions to build a complete picture.
# Newer data takes precedence for scalar values; lists are unioned and deduped.

CONCERN_LEVEL_ORDER = {"none": 0, "low": 1, "moderate": 2, "high": 3}


def _accumulate_financial_signals(lead_id) -> dict:
    """Merge financial signals across all interactions. Keep highest concern level."""
    artifacts = (
        ContextArtifact.objects
        .filter(lead_id=lead_id, artifact_type="financial_signals")
        .order_by("created_at")
    )
    result = {"concern_level": "none", "mentions": []}
    for a in artifacts:
        try:
            data = json.loads(a.content)
            level = data.get("concern_level", "none")
            if CONCERN_LEVEL_ORDER.get(level, 0) > CONCERN_LEVEL_ORDER.get(result["concern_level"], 0):
                result["concern_level"] = level
            result["mentions"].extend(data.get("mentions", []))
        except (json.JSONDecodeError, TypeError):
            pass
    result["mentions"] = list(dict.fromkeys(result["mentions"]))  # dedup
    return result


def _accumulate_scheduling_constraints(lead_id) -> dict:
    """Merge scheduling constraints across all interactions."""
    artifacts = (
        ContextArtifact.objects
        .filter(lead_id=lead_id, artifact_type="scheduling_constraints")
        .order_by("created_at")
    )
    constraints = []
    preferred_times = []
    for a in artifacts:
        try:
            data = json.loads(a.content)
            constraints.extend(data.get("constraints", []))
            preferred_times.extend(data.get("preferred_times", []))
        except (json.JSONDecodeError, TypeError):
            pass
    return {
        "constraints": list(dict.fromkeys(constraints)),
        "preferred_times": list(dict.fromkeys(preferred_times)),
    }


def _accumulate_family_context(lead_id) -> dict:
    """Merge family context across all interactions."""
    artifacts = (
        ContextArtifact.objects
        .filter(lead_id=lead_id, artifact_type="family_context")
        .order_by("created_at")
    )
    siblings = []
    decision_makers = []
    notes = []
    for a in artifacts:
        try:
            data = json.loads(a.content)
            siblings.extend(data.get("siblings", []))
            decision_makers.extend(data.get("decision_makers", []))
            notes.extend(data.get("notes", []))
        except (json.JSONDecodeError, TypeError):
            pass
    return {
        "siblings": list(dict.fromkeys(siblings)),
        "decision_makers": list(dict.fromkeys(decision_makers)),
        "notes": list(dict.fromkeys(notes)),
    }


def _accumulate_objections(lead_id) -> list:
    """
    Collect objections across all interactions.
    Deduplicate by topic, keeping the highest severity for each.
    """
    artifacts = (
        ContextArtifact.objects
        .filter(lead_id=lead_id, artifact_type="objections")
        .order_by("created_at")
    )
    SEVERITY_ORDER = {"low": 0, "moderate": 1, "high": 2}
    objections_by_topic = {}
    for a in artifacts:
        try:
            data = json.loads(a.content)
            for obj in data:
                topic = obj.get("topic", "unknown")
                severity = obj.get("severity", "low")
                existing = objections_by_topic.get(topic)
                if not existing or SEVERITY_ORDER.get(severity, 0) > SEVERITY_ORDER.get(existing.get("severity", "low"), 0):
                    objections_by_topic[topic] = obj
        except (json.JSONDecodeError, TypeError):
            pass
    return list(objections_by_topic.values())

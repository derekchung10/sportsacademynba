"""
LLM Service — handles all LLM calls with a pluggable provider (OpenAI or Mock).

Cost control strategy:
1. Use gpt-4o-mini (cheap, fast) for extraction tasks
2. Structured prompts with clear output format → fewer retries
3. Cache results as ContextArtifacts → never re-process the same interaction
4. Batch extraction into a single call per interaction (all dimensions in one prompt)

Context dimensions (Option D — structured extraction):
- Core: summary, facts, intent, sentiment, open_questions (original)
- Financial: cost concerns, scholarship interest, budget signals
- Scheduling: constraints, preferred times, conflicts
- Family: siblings, decision-maker dynamics
- Objections: specific concerns with severity
"""
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class LLMExtractionResult:
    """Structured output from LLM extraction — includes enriched context dimensions."""
    def __init__(
        self,
        summary: str,
        facts: list[str],
        intent: str,
        sentiment: str,
        open_questions: list[str],
        financial_signals: dict | None = None,
        scheduling_constraints: dict | None = None,
        family_context: dict | None = None,
        objections: list[dict] | None = None,
    ):
        self.summary = summary
        self.facts = facts
        self.intent = intent
        self.sentiment = sentiment
        self.open_questions = open_questions
        # Enriched context dimensions (Option D)
        self.financial_signals = financial_signals or {"concern_level": "none", "mentions": []}
        self.scheduling_constraints = scheduling_constraints or {"constraints": [], "preferred_times": []}
        self.family_context = family_context or {"siblings": [], "decision_makers": [], "notes": []}
        self.objections = objections or []


EXTRACTION_PROMPT = """You are an AI assistant for a sports academy outreach system.
Analyze the following interaction transcript and extract structured information.

CONTEXT:
- Lead: {lead_name} (parent/guardian)
- Child: {child_info}
- Sport: {sport}
- Academy: {academy_name}
- Campaign Goal: {campaign_goal}
- Channel: {channel} ({direction})
- Interaction Status: {status}

TRANSCRIPT:
{transcript}

Respond with ONLY valid JSON in this exact format:
{{
  "summary": "2-3 sentence summary of what happened in this interaction",
  "facts": ["fact 1 about the lead/child", "fact 2", ...],
  "intent": "one of: interested, considering, objecting, scheduling, requesting_info, declining, no_response, unclear",
  "sentiment": "one of: positive, neutral, negative",
  "open_questions": ["unanswered question 1", "question 2", ...],
  "financial_signals": {{
    "concern_level": "one of: none, low, moderate, high",
    "mentions": ["specific financial mention 1", ...]
  }},
  "scheduling_constraints": {{
    "constraints": ["e.g. busy weekends", "travels in June", ...],
    "preferred_times": ["e.g. weekday afternoons", "Saturday mornings", ...]
  }},
  "family_context": {{
    "siblings": ["e.g. younger sister age 9 interested in tennis", ...],
    "decision_makers": ["e.g. spouse not yet on board", "grandparent involved", ...],
    "notes": ["e.g. single parent", "recently relocated", ...]
  }},
  "objections": [
    {{"topic": "e.g. cost, distance, time, injury concern", "detail": "specific concern", "severity": "one of: low, moderate, high"}}
  ]
}}

Rules:
- Facts should be specific, actionable pieces of information (e.g., "Child plays travel soccer on weekends")
- Open questions are things we asked but didn't get answered, or things the lead asked that we need to follow up on
- financial_signals: Only populate if cost/price/budget/scholarship is mentioned. Otherwise concern_level is "none" with empty mentions.
- scheduling_constraints: Only populate if time/day/availability is discussed. Otherwise empty arrays.
- family_context: Only populate if siblings, other family members, or household dynamics are mentioned. Otherwise empty.
- objections: Only populate if the lead explicitly raises a concern or pushback. Each objection has a topic, detail, and severity.
- If the interaction was a no_answer/voicemail, provide minimal extraction (empty enriched fields).
- Be concise. Every token costs money. Only extract what's actually in the transcript — do NOT infer or hallucinate."""


def extract_from_interaction(
    transcript: str,
    lead_name: str,
    child_info: str,
    sport: str,
    academy_name: str,
    campaign_goal: str,
    channel: str,
    direction: str,
    status: str,
) -> LLMExtractionResult:
    """
    Single LLM call to extract summary, facts, intent, sentiment, open questions,
    and enriched context dimensions from a completed interaction.
    """
    if not transcript or status in ("no_answer", "failed"):
        # No transcript = no LLM call needed. Save cost.
        return LLMExtractionResult(
            summary=f"{channel.title()} {direction} — {status}. No conversation content.",
            facts=[],
            intent="no_response" if status == "no_answer" else "unclear",
            sentiment="neutral",
            open_questions=[],
        )

    prompt = EXTRACTION_PROMPT.format(
        lead_name=lead_name,
        child_info=child_info or "Unknown",
        sport=sport or "Unknown",
        academy_name=academy_name or "Sports Academy",
        campaign_goal=campaign_goal or "General outreach",
        channel=channel,
        direction=direction,
        status=status,
        transcript=transcript,
    )

    if settings.LLM_PROVIDER == "mock":
        return _mock_extraction(transcript, channel, direction, status)

    return _openai_extraction(prompt)


def _openai_extraction(prompt: str) -> LLMExtractionResult:
    """Call OpenAI API for extraction."""
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,  # Low temp for consistent extraction
            max_tokens=800,   # Increased cap for enriched dimensions
        )

        content = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0]

        data = json.loads(content)
        return LLMExtractionResult(
            summary=data.get("summary", ""),
            facts=data.get("facts", []),
            intent=data.get("intent", "unclear"),
            sentiment=data.get("sentiment", "neutral"),
            open_questions=data.get("open_questions", []),
            financial_signals=data.get("financial_signals"),
            scheduling_constraints=data.get("scheduling_constraints"),
            family_context=data.get("family_context"),
            objections=data.get("objections"),
        )
    except Exception as e:
        logger.error(f"OpenAI extraction failed: {e}")
        return LLMExtractionResult(
            summary="[LLM extraction failed — raw transcript available]",
            facts=[],
            intent="unclear",
            sentiment="neutral",
            open_questions=[],
        )


def _mock_extraction(transcript: str, channel: str, direction: str, status: str) -> LLMExtractionResult:
    """
    Mock LLM extraction for development/demo without API keys.
    Produces realistic-looking output based on simple heuristics,
    including enriched context dimensions.
    """
    transcript_lower = transcript.lower() if transcript else ""

    # Simple keyword-based heuristics for mock
    intent = "unclear"
    sentiment = "neutral"
    facts = []
    open_questions = []
    financial_signals = {"concern_level": "none", "mentions": []}
    scheduling_constraints = {"constraints": [], "preferred_times": []}
    family_context = {"siblings": [], "decision_makers": [], "notes": []}
    objections = []

    # ─── Intent & sentiment detection ──────────────────────────────────
    if any(w in transcript_lower for w in ["interested", "sounds great", "love to", "sign up", "excited"]):
        intent = "interested"
        sentiment = "positive"
    elif any(w in transcript_lower for w in ["schedule", "visit", "tour", "come by", "appointment"]):
        intent = "scheduling"
        sentiment = "positive"
    elif any(w in transcript_lower for w in ["think about", "consider", "not sure", "maybe", "let me"]):
        intent = "considering"
        sentiment = "neutral"
    elif any(w in transcript_lower for w in ["no thanks", "not interested", "don't", "can't afford", "too expensive"]):
        intent = "declining"
        sentiment = "negative"
    elif any(w in transcript_lower for w in ["how much", "what time", "where", "tell me more", "information"]):
        intent = "requesting_info"
        sentiment = "neutral"
    elif status == "voicemail":
        intent = "no_response"
        sentiment = "neutral"

    # ─── Facts extraction ──────────────────────────────────────────────
    if "soccer" in transcript_lower or "football" in transcript_lower:
        facts.append("Child is involved in soccer/football")
    if "basketball" in transcript_lower:
        facts.append("Child is involved in basketball")
    if "swimming" in transcript_lower:
        facts.append("Child does swimming")
    if "tennis" in transcript_lower:
        facts.append("Child plays tennis")
    if "weekend" in transcript_lower:
        facts.append("Weekends are relevant to scheduling")
    if "after school" in transcript_lower or "afternoon" in transcript_lower:
        facts.append("After-school availability mentioned")
    if any(w in transcript_lower for w in ["busy", "schedule conflict"]):
        facts.append("Has scheduling constraints")
    if "scholarship" in transcript_lower or "financial" in transcript_lower:
        facts.append("Financial considerations are a factor")

    # ─── Financial signals ─────────────────────────────────────────────
    if any(w in transcript_lower for w in ["can't afford", "too expensive", "budget", "costly"]):
        financial_signals = {
            "concern_level": "high",
            "mentions": ["Lead expressed affordability concerns"],
        }
        objections.append({
            "topic": "cost",
            "detail": "Lead indicated the program may be too expensive",
            "severity": "high",
        })
    elif any(w in transcript_lower for w in ["scholarship", "financial aid", "discount", "payment plan"]):
        financial_signals = {
            "concern_level": "moderate",
            "mentions": ["Lead asked about financial assistance options"],
        }
    elif any(w in transcript_lower for w in ["how much", "cost", "price", "fee"]):
        financial_signals = {
            "concern_level": "low",
            "mentions": ["Lead asked about pricing"],
        }

    # ─── Scheduling constraints ────────────────────────────────────────
    if any(w in transcript_lower for w in ["busy weekends", "weekends are", "saturday", "sunday"]):
        scheduling_constraints["constraints"].append("Weekend availability limited")
    if any(w in transcript_lower for w in ["after school", "afternoon", "3pm", "4pm"]):
        scheduling_constraints["preferred_times"].append("Weekday afternoons")
    if any(w in transcript_lower for w in ["traveling", "vacation", "out of town", "away"]):
        scheduling_constraints["constraints"].append("Has upcoming travel/absence")
    if any(w in transcript_lower for w in ["morning", "before school"]):
        scheduling_constraints["preferred_times"].append("Mornings")
    if any(w in transcript_lower for w in ["conflict", "overlap", "same time"]):
        scheduling_constraints["constraints"].append("Has time conflicts with other activities")

    # ─── Family context ────────────────────────────────────────────────
    if any(w in transcript_lower for w in ["brother", "sister", "sibling", "other child", "younger", "older"]):
        family_context["siblings"].append("Has sibling(s) who may also be interested")
    if any(w in transcript_lower for w in ["husband", "wife", "spouse", "partner"]):
        family_context["decision_makers"].append("Spouse/partner is part of the decision")
    if "single" in transcript_lower and "parent" in transcript_lower:
        family_context["notes"].append("Single parent household")
    if any(w in transcript_lower for w in ["grandparent", "grandmother", "grandfather"]):
        family_context["decision_makers"].append("Grandparent involved in decision-making")
    if any(w in transcript_lower for w in ["moved", "relocated", "new to the area", "just moved"]):
        family_context["notes"].append("Family recently relocated")

    # ─── Objections ────────────────────────────────────────────────────
    if any(w in transcript_lower for w in ["too far", "distance", "drive", "commute"]):
        objections.append({
            "topic": "distance",
            "detail": "Location or commute is a concern",
            "severity": "moderate",
        })
    if any(w in transcript_lower for w in ["injury", "hurt", "safety", "dangerous"]):
        objections.append({
            "topic": "safety",
            "detail": "Concerned about injury or safety risks",
            "severity": "moderate",
        })
    if any(w in transcript_lower for w in ["no time", "too busy", "overcommitted"]):
        objections.append({
            "topic": "time",
            "detail": "Family is time-constrained",
            "severity": "moderate",
        })

    # ─── Open questions ────────────────────────────────────────────────
    if "?" in transcript:
        open_questions.append("Lead asked questions that need follow-up")
    if intent == "requesting_info":
        open_questions.append("Lead requested more information — need to provide details")

    # ─── Summary ───────────────────────────────────────────────────────
    summary_prefix = f"{channel.title()} {direction} call" if channel == "voice" else f"{channel.upper()} {direction}"
    summary = f"{summary_prefix} - {status}. Lead appears {intent.replace('_', ' ')}."

    if facts:
        summary += f" Key info: {'; '.join(facts[:2])}."

    return LLMExtractionResult(
        summary=summary,
        facts=facts,
        intent=intent,
        sentiment=sentiment,
        open_questions=open_questions,
        financial_signals=financial_signals,
        scheduling_constraints=scheduling_constraints,
        family_context=family_context,
        objections=objections,
    )

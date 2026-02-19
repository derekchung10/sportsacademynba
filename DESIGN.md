# Academy Outreach Platform - Design Document

## How to Run / Demo

```bash
# 1. Setup backend
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1    # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt

# 2. Configure (mock LLM works out of the box - no API key needed)
cp .env.example .env
# Optionally set OPENAI_API_KEY and LLM_PROVIDER=openai for real LLM

# 3. Seed demo data
python seed_data.py

# 4. Start server
uvicorn app.main:app --reload --port 8000

# 5. Open
# Dashboard: http://localhost:8000
# API Docs:  http://localhost:8000/docs
```

### Quick Demo Script

1. Open http://localhost:8000 - see 6 leads in various states
2. Click **Sarah Mitchell** - see her timeline, 2 interactions, NBA recommending a voice call
3. Click **James Thompson** - see channel escalation (voice -> voicemail -> SMS) 
4. Click **Maria Rodriguez** - see inbound interest flagged as urgent priority
5. Click **Priya Patel** - brand new lead, NBA recommends initial outreach
6. Try the **Interactions** tab to see transcripts and LLM-extracted signals
7. Try the **Context** tab to see assembled context artifacts
8. Try the **NBA History** tab to see how decisions evolved
9. Use search to filter leads, click status badges to filter by status
10. Hit http://localhost:8000/api/context/{lead_id}/prepare-outbound-call to see the context injection boundary

Submit a new interaction via the API docs (`POST /api/interactions/`) and watch the system process it end-to-end.

---

## System Overview

```
                     Operator Dashboard (HTML/Alpine.js/Tailwind)
                                    |
                              REST API (FastAPI)
                                    |
            +-----------+-----------+-----------+-----------+
            |           |           |           |           |
        Lead API   Interaction  Context API   NBA API    Health
                   Entrypoint
                       |
              Interaction Processor (orchestrator)
              /         |          \
     LLM Service   Context        NBA Engine
     (extract)     Enrichment     (rule-based)
                   (persist)
                       |
                   SQLite DB
            (event log + materialized views)
                       |
              Provider Stubs
              (voice/SMS context injection boundary)
```

### Components & Boundaries

| Component | Responsibility | Interface |
|-----------|---------------|-----------|
| **Lead API** | CRUD, search/filter, detail views | REST `/api/leads/` |
| **Interaction Entrypoint** | Accept completed interactions, trigger pipeline | REST `POST /api/interactions/` |
| **Interaction Processor** | Orchestrate: log -> extract -> enrich -> update -> NBA | Internal, called by API |
| **LLM Service** | Summarization, fact extraction, intent/sentiment detection, enriched context extraction | `extract_from_interaction()` |
| **Context Service** | Persist artifacts + assemble context packs (incl. enriched dimensions) | `enrich_from_extraction()`, `assemble_context_pack()` |
| **NBA Engine** | Deterministic rule-based next-action decisions (context-aware) | `compute_nba()` |
| **Provider Stubs** | Voice/SMS context injection boundary | REST `/api/context/{id}/prepare-*` |
| **Operator Dashboard** | Visual inspection of lead state and decisions | HTML served at `/` |

---

## Assumptions

1. **Traffic**: Low-to-medium volume (hundreds to low thousands of leads). SQLite is sufficient; would migrate to PostgreSQL for production scale.
2. **Reliability**: Single-server deployment. In production, the processing pipeline would be async (task queue) with retries. For this demo, synchronous processing is simpler and more inspectable.
3. **Interaction source**: Interactions arrive as completed events (post-call/post-SMS). The system doesn't manage live calls — it receives results and decides what's next.
4. **LLM availability**: LLM calls can fail. The system gracefully degrades (stores raw transcript, flags extraction as failed, still produces NBA from available data).
5. **Time**: All timestamps are UTC. Scheduling uses simple hour-based offsets. Production would need timezone-aware scheduling per lead.
6. **Academy context**: Single academy, multiple sports. The data model supports multi-academy but the NBA rules assume a single campaign per lead.

---

## Decisions & Trade-offs

### Django + PostgreSQL (over FastAPI + SQLite)

**Chose**: Django with Django REST Framework and PostgreSQL.

**Why**:
- Django ORM provides a mature, well-documented data layer with migrations built-in.
- PostgreSQL supports concurrent writes, proper transactions, and scales to production without a swap.
- DRF provides standardized serialization, validation, and view patterns.
- Django's ecosystem (admin, management commands, middleware) provides free infrastructure.

**Trade-off**: Django is heavier than FastAPI. No auto-generated API docs (Swagger) without adding `drf-spectacular`. Synchronous by default (async is possible but less idiomatic in Django).

**PostgreSQL-native features used**:
- `JSONField` for structured data (event payloads, extracted facts, open questions, NBA policy inputs, tags) -- enables native JSON queries and avoids manual `json.dumps`/`json.loads`.
- Compound database indexes on hot query paths (`lead + is_current`, `lead + created_at`, `status + scheduled_at`) for dashboard performance.
- `USE_TZ = True` with timezone-aware UTC datetimes throughout.

### Event Log + Materialized Views (Hybrid)

**Chose**: Append-only event log as source of truth, with materialized fields on the Lead model for fast reads.

**Why**: The event log enables full timeline reconstruction and audit trail. Materialized counters (total_interactions, total_voice_attempts) on the Lead model avoid expensive aggregation queries for the dashboard and NBA engine.

**Trade-off**: Dual-write (event + lead update) means we need to keep them in sync. Acceptable at this scale within a single transaction. At larger scale, would use event-driven projections.

**Rejected**: Pure event sourcing (rebuild all state from events on every read) — too expensive for dashboard queries at this stage.

### Deterministic NBA (Rules, not LLM)

**Chose**: Rule-based policy engine for NBA decisions. LLM provides context (summaries, intent, enriched dimensions); rules provide decisions.

**Why**: 
- **Reproducibility**: Same inputs always produce the same output. Critical for debugging and operator trust.
- **Testability**: Rules can be unit tested without mocking LLM.
- **Cost**: No LLM call for decisioning — only for extraction.
- **Auditability**: Each decision includes the rule name and a snapshot of policy inputs.

**Trade-off**: Rules are less flexible than LLM-based reasoning. Complex nuances in conversations might be missed. The rule set covers the 80% case; edge cases need human review.

**Rejected alternatives**:
- **LLM-based NBA** ("given this context, what should we do next?") — non-deterministic, expensive, hard to audit, hard to test. Two operators would get different recommendations for the same lead.
- **ML scoring model** (predict P(enroll) → rank leads) — requires historical conversion data we don't have yet. Cold-start problem. Would be a great Phase 2 once we have outcome data.
- **Hybrid LLM + rules** (LLM suggests, rules constrain) — interesting but adds latency and cost to every decision. Could be useful for edge cases the rules can't handle.

### Enriched Context Extraction — Structured Dimensions

**Chose**: Expand the single LLM extraction call to also pull structured context dimensions: financial signals, scheduling constraints, family context, and objections. Store them as typed `ContextArtifact` records. Feed them into new context-aware NBA rules.

**Why**: The original extraction (summary, facts, intent, sentiment, open questions) captures *what happened* but misses *why* the lead is hesitating or *what* their real-world constraints are. A parent who says "I'll think about it" might mean:
- "I can't afford it" (financial)
- "My kid's weekends are already full" (scheduling)
- "I need to talk to my spouse" (decision-maker)
- "I'm worried about injuries" (safety objection)

Each of these requires a *completely different* follow-up. Without structured extraction, the NBA treats them all the same ("considering" → generic nudge SMS). With it, the system can:
- Send scholarship info to cost-concerned leads
- Offer flexible scheduling to time-constrained families
- Suggest a family-friendly touchpoint when a spouse needs to be involved
- Proactively address safety concerns with program materials

**New context dimensions extracted**:

| Dimension | What's extracted | Stored as |
|-----------|-----------------|-----------|
| Financial signals | `concern_level` (none/low/moderate/high), specific mentions | `financial_signals` artifact |
| Scheduling constraints | Time/day constraints, preferred windows | `scheduling_constraints` artifact |
| Family context | Siblings (potential additional enrollments), decision-makers, household notes | `family_context` artifact |
| Objections | Topic (cost, distance, safety, time), detail, severity | `objections` artifact |

**New NBA rules that consume enriched context**:

| Rule | Fires when | Action | Rationale |
|------|-----------|--------|-----------|
| `financial_concern_outreach` | Financial concern >= moderate | Send scholarship/aid info | Address cost barrier before it becomes a rejection |
| `address_objections` | Unaddressed objections exist (non-cost) | Send targeted info | Specific concern-handling converts better than generic follow-ups |
| `engage_decision_maker` | Other decision-maker pending + lead considering/interested | Suggest family touchpoint | Closing without all stakeholders risks reversal |
| `sibling_opportunity` | Has siblings + lead is interested/positive | Mention multi-child options | High-value expansion, but only when timing is right |

**Accumulation strategy**: Context dimensions are accumulated across all interactions, not just the latest:
- Financial: highest concern level across all interactions is kept
- Scheduling: all constraints and preferences are unioned
- Family: siblings, decision-makers, notes are merged and deduped
- Objections: deduped by topic, highest severity kept per topic

#### Trade-offs of Storing More Specific Context Information

**Cost**: The enriched prompt adds ~150 tokens of output per call (~$0.00009 extra with gpt-4o-mini). At 1000 interactions/day this is ~$0.09/day — negligible. The real cost is in storage and complexity.

**Accuracy vs. hallucination risk**: The more specific the extraction target, the higher the risk of hallucination. Asking "what is the financial concern level?" on a transcript that never mentions money will sometimes produce a false positive ("low concern" when there's no signal). We mitigate this by:
- Explicit prompt instruction: "Only extract what's actually in the transcript — do NOT infer or hallucinate"
- Storing only non-empty dimensions (no artifact created when there's nothing to extract)
- Accumulation uses "highest severity wins" — avoids diluting real signals with noise

**Complexity**: Each new dimension adds:
- Extraction prompt surface area (more output to parse, more things that can be malformed)
- Storage (new artifact types, accumulation logic across interactions)
- NBA rules (more branches, more edge cases to test)
- Context pack assembly (more data to gather and format)

**Why these 4 dimensions** — they cover the most common sales-blocking scenarios in outreach:
1. **Can they afford it?** (financial signals)
2. **Can they make time?** (scheduling constraints)
3. **Is everyone on board?** (family/decision-maker context)
4. **Are there specific fears?** (objections)

**What we chose NOT to extract** (and why):
- **Child's academic performance**: Rarely mentioned in outreach calls; low signal, high hallucination risk
- **Competitive academy interest**: Useful but adversarial — could bias agent behavior in harmful ways
- **Parent's occupation/income**: Sensitive PII; inference would be unreliable and ethically questionable
- **Specific hobby details** (e.g., "plays violin on Tuesdays"): Too granular to act on systematically; better left in free-text facts

**Design principle**: Extract dimensions the NBA rules can act on. If there's no rule that would use the dimension, don't extract it — it's just noise that costs money and adds hallucination risk.

### Single LLM Call Per Interaction

**Chose**: One batched prompt that extracts all dimensions (core + enriched) in a single call.

**Why**: Cost control. A single `gpt-4o-mini` call (~$0.001) vs. separate calls per dimension (~$0.005+). Results are cached as context artifacts — never re-processed.

**Trade-off**: The single prompt is slightly less precise than specialized prompts per extraction type. The enriched dimensions add ~150 output tokens. Good enough for the use case — specialized prompts would only make sense if we needed higher precision on a specific dimension.

### Context Artifacts (Persist, Don't Recompute)

**Chose**: Persist LLM extraction results as versioned `ContextArtifact` records. Context packs assembled on-demand from stored artifacts. Enriched dimensions are accumulated across interactions to build a complete picture.

**Why**: 
- LLM called once per interaction (cost control)
- Artifacts are traceable (we know exactly what context was available at any point)
- Context assembly is a fast DB read, not an LLM call
- Accumulation lets context build over time (financial concern from call #2 + scheduling constraint from call #4 both influence call #5's NBA)

**What I didn't build**: Context summarization across multiple interactions (a "mega-summary" that condenses 10 interactions into a paragraph). Would be valuable for leads with many interactions to keep context packs concise.

### Synchronous Processing Pipeline

**Chose**: Synchronous pipeline (API call -> process -> respond). 

**Why**: Simpler to reason about, easier to demo, full result in the API response.

**Trade-off**: Blocks the HTTP response while LLM processes (~1-2s with real API, instant with mock). Production should use background tasks (Celery, or even FastAPI BackgroundTasks).

---

## Risks / What Breaks First

1. **LLM extraction quality degrades**: If the LLM misclassifies intent (e.g., "considering" as "interested"), the NBA overreacts. **Mitigation**: Conservative rules (err on the side of waiting), human review for high-stakes actions, sentiment as a secondary signal.

2. **Over-contacting leads**: Without robust scheduling enforcement, a bug could trigger too-frequent outreach. **Mitigation**: Cool-down rules in NBA, max attempts per channel, all scheduled actions are inspectable.

3. **SQLite concurrency**: Under concurrent load, SQLite write locks could bottleneck. **Mitigation**: Move to PostgreSQL. The ORM layer abstracts this — it's a config change.

4. **Context pack grows unbounded**: Leads with 50+ interactions accumulate large fact sets and context. **Mitigation**: Fact deduplication (implemented), version-based artifact superseding (implemented), eventual need for summarization/compression.

---

## Deep Dive 1: Context Injection Boundary

### Why this matters

The hardest integration problem in outreach automation isn't the decisioning — it's getting the right context to the right agent at the right time. A voice AI agent with no context sounds robotic; one with stale context is worse.

### Design

The "context injection boundary" is the interface between our system and the voice/SMS provider. I modeled it as a **context pack** — a structured JSON payload assembled on-demand:

```json
{
  "lead_name": "Sarah Mitchell",
  "child_info": "Jake Mitchell (age 14)",
  "campaign_goal": "Enroll in summer basketball intensive",
  "current_status": "interested",
  "latest_summary": "Voice outbound - completed. Lead is interested...",
  "known_facts": ["Child plays basketball", "Asked about cost", "Wants campus visit"],
  "open_questions": ["Lead asked about early bird discounts"],
  "financial_signals": { "concern_level": "moderate", "mentions": ["Asked about scholarship options"] },
  "scheduling_constraints": { "constraints": ["Busy weekends"], "preferred_times": ["Weekday afternoons"] },
  "family_context": { "siblings": ["Younger sister age 9"], "decision_makers": ["Spouse not yet on board"] },
  "objections": [{ "topic": "distance", "detail": "30-minute drive", "severity": "low" }],
  "recent_interactions": [...],
  "current_nba": { "action": "call", "reasoning": "..." }
}
```

**Where context comes from**:
- `lead_name`, `child_info`, `campaign_goal` → Lead record (operator-entered)
- `latest_summary`, `known_facts`, `open_questions` → ContextArtifact table (LLM-derived, persisted)
- `financial_signals`, `scheduling_constraints`, `family_context`, `objections` → ContextArtifact table (enriched dimensions, accumulated across interactions)
- `recent_interactions` → Interaction table (last 5)
- `current_nba` → NBADecision table (latest active decision)

**How it's attached at call time**:
- **Outbound call**: Provider stub calls `GET /api/context/{id}/prepare-outbound-call`. Returns context pack + agent instructions (a prompt built from the pack). In production, this would be a webhook the voice provider calls before dialing.
- **Inbound call**: On caller-ID match, same endpoint is called to hydrate context before the agent answers.

**Failure mode handled**: If context assembly fails (DB down, lead not found), the system returns a minimal context pack with just the lead name and phone. The agent can still make/take the call — just with less context. This is better than failing the call entirely.

### What I'd improve

- TTL on context packs (invalidate after N minutes to force refresh)
- Context compression for leads with long histories
- A/B testing different context pack formats against call outcomes
- Signal decay: reduce weight of old enriched signals after N days without reinforcement


## Deep Dive 2: NBA Policy Engine Testability & Reproducibility

### Why this matters

The NBA decision is the most consequential output of the system — it determines what happens to a real person. If it's wrong (over-contacts, under-contacts, wrong channel), trust erodes fast. Operators need to understand **why** a decision was made and be able to **reproduce** it.

### Design

Every NBA decision persists:
1. **The decision itself**: action, channel, priority, scheduled_for
2. **The reasoning**: Human-readable explanation ("Lead expressed intent to schedule. Call immediately...")
3. **The rule name**: Which specific rule fired (`scheduling_request`, `channel_escalation_to_sms`, `financial_concern_outreach`)
4. **Policy inputs snapshot**: A JSON dump of every input the rule engine evaluated (including enriched context signals)

This means an operator can:
- See the decision and reasoning in the dashboard
- Trace back to the exact rule
- See the exact state at decision time (policy_inputs)
- Reproduce the decision by feeding those inputs back into the engine

### Rule priority & evaluation

Rules are evaluated in strict priority order (first match wins):

1. Terminal states (enrolled, declined) → no action
2. Opt-out → no action  
3. Inbound interest → urgent callback
4. Scheduling request → immediate action
5. Info request → send info via SMS
6. **Financial concern → send scholarship/aid info** *(context-aware)*
7. **Unaddressed objections → send targeted info** *(context-aware)*
8. **Pending decision-maker → suggest family touchpoint** *(context-aware)*
9. **Sibling opportunity → mention multi-child options** *(context-aware)*
10. Positive engagement → follow up call
11. Considering → gentle SMS nudge  
12. Objecting → soft follow up or stop
13. Channel escalation → switch channels after N failures
14. Voicemail → SMS follow up
15. No answer → retry with cooldown
16. Cool-down → wait if too recent
17. New lead → initial outreach
18. Default → standard follow up

Rules 6-9 are the **context-aware rules** that consume enriched dimensions. They sit between immediate-response rules (highest priority) and generic engagement rules. This means: if a lead is interested AND has financial concerns, the financial concern rule fires first — addressing the barrier takes priority over a generic follow-up call.

### Failure mode handled

**Stale NBA**: If a lead's circumstances change (e.g., they call in while we have a "wait" NBA), the inbound interaction triggers recomputation. The old NBA is marked "superseded" and a new one is produced. The NBA history tab shows the full evolution.

**Missing enriched context**: If the LLM fails to extract enriched dimensions (API error, malformed JSON), the system falls through to the original rules. Context-aware rules simply don't match when their inputs are empty — no crash, no degraded behavior.

**Conflicting signals**: If sentiment is negative but intent is "interested" (sarcasm? data quality?), the rules evaluate intent first (it's more actionable). Sentiment serves as a tiebreaker, not a primary driver.

### What I'd improve

- Rule weighting/scoring instead of first-match-wins (allows nuanced combination)
- Operator override capability (mark an NBA as "rejected" with reason)
- Feedback loop: track whether NBA actions led to good outcomes, adjust rule priority

---

## LLM Usage

### Prompts & Outputs

Single extraction prompt per interaction. The prompt includes lead context (name, child, sport, campaign goal) so the LLM can produce relevant extractions. Output is structured JSON with 9 fields: summary, facts, intent, sentiment, open_questions, financial_signals, scheduling_constraints, family_context, objections.

Low temperature (0.1) for consistency. Max 800 output tokens to cap cost (increased from 500 to accommodate enriched dimensions).

### Cost Control Strategy

1. **gpt-4o-mini**: ~$0.15/1M input, $0.60/1M output tokens. An extraction call ~600 input + 350 output tokens ≈ $0.0002/interaction.
2. **One call per interaction**: Batched extraction (core + enriched) in a single call.
3. **Skip when no transcript**: No-answer and failed calls don't trigger LLM.
4. **Cache as artifacts**: Results persisted permanently, never re-extracted.
5. **Mock provider**: Development/testing uses zero API calls.
6. **Selective storage**: Enriched dimensions only stored when non-empty (no artifact for "no financial signal").

At 1000 interactions/day: ~$0.30/day in LLM costs.

---

## What I'd Do With One More Day

1. **Real OpenAI integration testing** with diverse transcript samples
2. **Webhook simulation** — actually execute scheduled actions and loop them back as new interactions
3. **Operator actions** — let operators override NBA, add notes, manually change status
4. **Metrics dashboard** — conversion funnel, response rates by channel, NBA accuracy
5. **WebSocket updates** — real-time dashboard updates when interactions are processed
6. **Test suite** — unit tests for NBA rules (easy since they're deterministic), integration tests for the processing pipeline
7. **Multi-academy support** — scope leads and campaigns per academy

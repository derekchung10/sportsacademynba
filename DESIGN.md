# Academy Outreach Platform — Design Document

## How to Run / Demo

```bash
# 1. Setup backend
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure (mock LLM works out of the box — no API key needed)
cp .env.example .env
# Optionally set OPENAI_API_KEY and LLM_PROVIDER=openai for real LLM

# 3. Run migrations and seed
python manage.py migrate
python manage.py seed_q_table     # Seed RL Q-table with domain priors
python manage.py setup_sms_sweep  # Register periodic SMS batch flush task
python seed_data.py               # Seed demo leads + interactions

# 4. Start server
python manage.py runserver 8001

# 5. (Optional) Start background worker for SMS batch flushing
python manage.py qcluster

# 6. Start frontend
cd ../frontend
npm install
npm run dev

# Dashboard: http://localhost:5174
```

### Quick Demo Script

1. Open http://localhost:5174 — see leads in various lifecycle states
2. Click a lead to see their timeline, interactions, context artifacts, and NBA decisions
3. Check the **NBA History** tab to see how the RL engine's decisions evolve over interactions
4. Submit a new interaction via `POST /api/interactions/` — watch the full pipeline: LLM extraction → context enrichment → Q-table update → RL action selection → action brief generation
4b. Or submit individual SMS messages via `POST /api/interactions/sms` — they buffer until the thread goes quiet, then flush as a single batch extraction
5. Hit `/api/nba/{lead_id}/current` to see the full action brief: semantic action, content directives, tone, things to avoid, timing rationale, and message draft
6. Hit `/api/context/{lead_id}/prepare-outbound-call` to see the context injection boundary

### Inspecting the RL Engine

```bash
python manage.py shell
```

```python
from app.models import QValue, StateTransition

# Top learned Q-values
for q in QValue.objects.order_by('-q_value')[:15]:
    print(f"Q({q.state}, {q.action}) = {q.q_value:.4f}  (tried {q.visit_count}x)")

# Learning history
for t in StateTransition.objects.order_by('-created_at')[:10]:
    print(f"{t.state_before} --[{t.action_taken}]--> {t.state_after}  r={t.reward:+.2f}")
```

---

## System Overview

```
                     Operator Dashboard (React 18/Tailwind CSS/Vite)
                                    |
                              REST API (Django REST Framework)
                                    |
            +-----------+-----------+-----------+-----------+
            |           |           |           |           |
        Lead API   Interaction  Context API   NBA API    Comms
                   Entrypoint
                       |
              Interaction Processor (orchestrator)
              /         |         |          \
     LLM Service   Context    Q-Table      NBA Engine
     (extract)     Enrichment  Update      (RL + Briefs)
                   (persist)  (learn)
                       |
                   SQLite / PostgreSQL
            (event log + materialized views + Q-table)
                       |
              Provider Stubs
              (voice/SMS context injection boundary)
```

### Components & Boundaries

| Component | Responsibility | Interface |
|-----------|---------------|-----------|
| **Lead API** | CRUD, search/filter, detail views | REST `/api/leads/` |
| **Interaction Entrypoint** | Accept completed interactions, trigger pipeline | REST `POST /api/interactions/` |
| **SMS Batch Buffer** | Buffer individual SMS messages, flush thread when quiet | REST `POST /api/interactions/sms` |
| **Interaction Processor** | Orchestrate: log → extract → enrich → Q-update → NBA | Internal, called by API |
| **LLM Service** | Extract summary, facts, intent, sentiment, enriched dimensions, open-ended signals | `extract_from_interaction()` |
| **Context Service** | Persist artifacts + assemble context packs | `enrich_from_extraction()`, `assemble_context_pack()` |
| **RL Engine** | State encoding, Q-learning, UCB action selection | `encode_state()`, `select_action()`, `update_q_table()` |
| **Action Briefs** | Semantic action templates + context-enriched brief builder | `build_action_brief()` |
| **NBA Engine** | Orchestrate RL + briefs, hard overrides, persist decisions | `compute_nba()`, `persist_nba_decision()` |
| **Provider Stubs** | Voice/SMS context injection boundary | REST `/api/context/{id}/prepare-*` |
| **Operator Dashboard** | Visual inspection of lead state and decisions | HTML served at `/` |

---

## Assumptions

1. **Traffic**: Low-to-medium volume (hundreds to low thousands of leads). SQLite is sufficient for development; PostgreSQL for production.
2. **Reliability**: Single-server deployment. In production, the processing pipeline would be async (task queue) with retries.
3. **Interaction source**: Interactions arrive as completed events (post-call/post-SMS). The system doesn't manage live calls — it receives results and decides what's next.
4. **LLM availability**: LLM calls can fail. The system gracefully degrades: stores raw transcript, flags extraction as failed, still produces an NBA from available data.
5. **Time**: All timestamps are UTC. Scheduling uses hour-based offsets. Production would need timezone-aware scheduling per lead.
6. **Learning data**: The Q-table starts with hand-seeded priors and learns from observed outcomes. Early behavior is guided by domain knowledge; long-term behavior is shaped by data.

---

## Decisions & Trade-offs

### Graph RL for NBA Decisioning (over Rule-Based)

**Chose**: A graph reinforcement learning engine that models the lead lifecycle as a state-transition graph and learns optimal actions via tabular Q-learning.

**Why**:
- **Trajectory optimization**: Rules optimize one step ("what's the best next action?"). The RL engine optimizes the full trajectory ("what sequence of actions maximizes the chance this lead reaches enrolled/active?"). It can learn that "wait" now leads to better conversion later — something a rule engine can never discover.
- **Adaptive**: Weights learn from outcomes. Actions that consistently lead to lead progression get reinforced; actions that correlate with regression get penalized. The system improves over time without manual rule tuning.
- **Deterministic**: Same Q-table + same state = same action. Q-values only change via the update step (after observing outcomes), not during selection. Fully auditable.
- **Composable**: RL picks the *strategy* (which semantic action); the action brief layer generates the *tactics* (what to say, tone, prep). These concerns are cleanly separated.

**What we considered but didn't go with**:

#### Why Not First-Match Rule Engine?

We initially built a deterministic rule engine with 22 hand-crafted rules evaluated in priority order (first match wins). This had several limitations:

- **Arbitrary ordering**: Why should `financial_concern` (rule 10) beat `positive_engagement` (rule 14)? The ordering was a product of developer intuition, not data.
- **No multi-signal blending**: If a lead is interested AND has financial concerns AND was referred by a friend, the rule engine picks exactly one rule and ignores the others. The real optimal action should blend all signals.
- **No learning**: When a rule consistently led to bad outcomes, nothing changed. A developer had to manually notice, investigate, and re-order rules.
- **Brittle to new signals**: Adding the `additional_signals` (open-ended LLM extraction for unknown unknowns) required bolting on an `_llm_advisor` fallback — a band-aid that didn't compose with the existing rules.
- **Action vocabulary too shallow**: Rules produced "call" or "sms" — just a channel, with no guidance on what to say, what tone to use, or what to avoid.

#### Why Not a Weighted Linear Model?

We also considered replacing first-match-wins with a weighted scoring model (perceptron): each signal gets a weight (0–1, summing to 1), and the action with the highest weighted score wins. This would have solved the multi-signal problem but:

- **One-step optimization only**: It scores immediate actions but has no concept of trajectory. It can't learn that patience at the `interested` stage leads to better conversion at `trial`.
- **No temporal credit assignment**: If a lead converts after 5 interactions, which of those 5 actions deserves credit? A linear model has no mechanism for this.
- **Weights are decoupled from outcomes**: The learning signal (lead progression) maps poorly to individual signal weights without a state-transition model.

Graph RL solves all three: the Q-table captures multi-step value, the Bellman update assigns temporal credit, and the reward function ties directly to funnel progression.

### State Design: (lead_status, context_bucket)

**Chose**: ~90 discrete states = 9 lead statuses × 10 context buckets.

**Why**: Small enough for tabular Q-learning (no neural networks needed), large enough to capture meaningful situational differences. A lead who is `interested:financial_concern` should get a different action than one who is `interested:positive_engagement` — and both should differ from `at_risk:negative`.

**Context buckets** (priority-ordered, first match):
1. `unreached` — last interaction was no_answer/voicemail
2. `negative` — declining + negative sentiment
3. `scheduling_intent` — explicit scheduling request
4. `positive_engagement` — interested/scheduling + positive sentiment
5. `financial_concern` — moderate/high financial signals
6. `has_objections` — unaddressed non-financial objections
7. `family_context` — pending decision-makers or siblings
8. `considering` — on the fence
9. `novel_signal` — additional_signals with moderate+ urgency
10. `neutral` — no strong signal

**Trade-off**: Bucketing loses information. A lead with both financial concerns AND objections gets bucketed as `financial_concern` (higher priority). The content enrichment layer partially compensates — the action brief still includes objection-related directives even when the RL state doesn't encode them. With more data, we could expand the state space to capture compound signals.

### Semantic Actions (over Raw Channels)

**Chose**: 12 semantic actions that describe *what to do and why*, not just which channel to use.

| Action | Channel | Purpose |
|--------|---------|---------|
| `warm_follow_up` | voice | Build rapport, show genuine interest |
| `scheduling_push` | voice | Actively book a visit/trial |
| `scholarship_outreach` | sms | Share financial aid info |
| `info_send` | sms/email | Send requested program details |
| `gentle_nudge` | sms | Low-pressure reminder |
| `objection_address` | sms | Targeted concern handling |
| `welcome_onboard` | sms | First-session prep for new enrollees |
| `retention_check_in` | voice | Ask how the child is enjoying the program |
| `family_engage` | voice | Include other decision-makers |
| `channel_switch` | varies | Try a different channel after failures |
| `wait` | none | Strategically give space |
| `stop` | none | Cease outreach |

**Why**: "Send an SMS" is useless guidance. "Send scholarship info via SMS with an empathetic tone, include concrete numbers not vague 'affordable' language, and don't lead with full sticker price" is actionable. Each semantic action maps to a full **action brief** with content directives, tone, info to prepare, things to avoid, timing rationale, and a message draft.

**Trade-off**: 12 actions × 90 states = 1,080 Q-table entries. Very manageable, but it means the RL can't discover entirely new action types — only learn which existing ones work best in which states. Adding a new semantic action requires defining its template and re-seeding.

### UCB Action Selection (over Epsilon-Greedy)

**Chose**: Upper Confidence Bound (UCB) for balancing exploitation and exploration.

**Why**: Epsilon-greedy picks random actions with probability ε. In a customer-facing system, a random action (e.g., `stop` when the lead is interested) has a real cost. UCB gives a natural exploration bonus to under-tried actions that decays as they're tested — no random actions on real leads, just intelligent curiosity about under-explored paths.

### Action Briefs: Strategy + Tactics Separation

**Chose**: The RL engine picks *strategy* (which semantic action to take); a separate action brief builder generates *tactics* (what to say, how to say it).

**Why**: This separation means the RL doesn't need to learn content — it learns which *type* of action works in which state. Content generation is handled by templates enriched with the lead's specific context signals.

Each action brief includes:
- **Content directives**: Ordered talking points, each tied to a signal (e.g., "Mention scholarship options" from `financial_concern`, "Acknowledge referral" from `referral_source`)
- **Overall tone**: empathetic, enthusiastic, informational, gentle, warm
- **Info to prepare**: Materials the rep should have ready before the interaction
- **Things to avoid**: Guardrails (e.g., "don't lead with full sticker price", "don't hard-sell")
- **Timing rationale**: Human-readable explanation of why this timing
- **Message draft**: For SMS/email, a ready-to-send template incorporating all directives

Context enrichment adds directives from any active signal, regardless of which semantic action was chosen. If the RL picks `warm_follow_up` for a lead with financial concerns and a referral source, the brief will include the base warm_follow_up directives *plus* "be mindful of cost" and "acknowledge the referral."

### Q-Learning Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Learning rate (α) | 0.1 | Moderate — learns from experience without overreacting to noise |
| Discount factor (γ) | 0.9 | Values future rewards strongly — a patient approach that optimizes trajectories |
| UCB coefficient (C) | 1.0 | Balanced exploration — tunable based on lead volume |
| Q-value floor | 0.0 (default) | Untried actions start at 0; UCB bonus drives exploration |
| Q-value ceiling | None | No hard cap — successful actions can accumulate high values |

### Reward Function

Not all state transitions are equal. Rewards reflect business value:

| Transition | Reward | Rationale |
|------------|--------|-----------|
| new → contacted | +0.1 | Made contact, minimal value |
| contacted → interested | +0.4 | Meaningful engagement |
| interested → trial | +0.7 | Committed to trying |
| trial → enrolled | +1.0 | Conversion — the primary goal |
| enrolled → active | +0.3 | Retention success |
| active → at_risk | -0.5 | Regression |
| at_risk → inactive | -0.7 | Losing them |
| at_risk → active | +0.5 | Recovery (hard and valuable) |
| inactive → at_risk | +0.3 | Re-engagement signal |
| any → declined | -1.0 | Terminal negative |
| same → same | -0.02 | Small penalty for stalling |

### Cold Start: Seeded from Domain Knowledge

The Q-table is seeded with ~65 initial values derived from the original rule engine's priorities. This means day-1 behavior is at least as good as hand-crafted rules, then improves as outcomes are observed.

```bash
python manage.py seed_q_table          # Seed initial values
python manage.py seed_q_table --reset  # Clear and re-seed
```

---

## LLM Usage

### Extraction (One Call Per Interaction)

Single prompt extracts 10 structured dimensions from the conversation transcript:

| Dimension | What's extracted | How the system uses it |
|-----------|-----------------|----------------------|
| Summary | 2-3 sentence overview | Displayed to operators, used in context packs |
| Facts | Specific actionable information | Accumulated across interactions, shown in context packs |
| Intent | interested / considering / objecting / scheduling / requesting_info / declining / no_response / unclear | Drives lead status transitions, feeds RL state encoding |
| Sentiment | positive / neutral / negative | Modifies RL context bucket, influences tone selection |
| Open questions | Unanswered questions from either side | Shown in context pack so next agent can address them |
| Financial signals | Concern level (none/low/moderate/high) + mentions | Drives `financial_concern` context bucket, triggers scholarship content |
| Scheduling constraints | Time/day constraints + preferred windows | Enriches action briefs with scheduling awareness |
| Family context | Siblings, decision-makers, household notes | Drives `family_context` bucket, enables family_engage action |
| Objections | Topic, detail, severity per objection | Drives `has_objections` bucket, enables objection_address action |
| Additional signals | Open-ended: anything the LLM notices outside the fixed schema | Drives `novel_signal` bucket, enriches briefs with suggested actions |

The `additional_signals` field is specifically designed to capture unknown unknowns — life events (job loss, divorce), competitive offers, special needs, referral sources, or anything else a thoughtful rep would want to know. The LLM surfaces signals we didn't think to ask for.

### Cost Control

1. **gpt-4o-mini**: ~$0.15/1M input, $0.60/1M output. ~$0.0003/interaction.
2. **One call per interaction**: All dimensions extracted in a single batched prompt.
3. **SMS batch extraction**: Individual SMS messages are buffered and flushed as a single thread — one LLM call per conversation, not per message. A 10-message SMS exchange costs the same as one voice call extraction.
4. **Skip when no transcript**: No-answer and failed calls don't trigger LLM.
5. **Cache as artifacts**: Results persisted permanently, never re-extracted.
6. **Mock provider**: Development/testing uses zero API calls.
7. **RL advisor call** (optional): When the `novel_signal` bucket is active and in OpenAI mode, a lightweight second LLM call (~200 tokens) recommends an action. In mock mode, the signal's `suggested_action` field is used directly — zero cost.

---

## Deep Dive 1: Context Injection Boundary

The "context injection boundary" is the interface between our system and the voice/SMS provider. A context pack is assembled on-demand from stored artifacts:

```json
{
  "lead_name": "Sarah Mitchell",
  "child_info": "Jake Mitchell (age 14)",
  "campaign_goal": "Enroll in summer basketball intensive",
  "current_status": "interested",
  "latest_summary": "Voice outbound - completed. Lead is interested...",
  "known_facts": ["Child plays basketball", "Asked about cost"],
  "open_questions": ["Lead asked about early bird discounts"],
  "financial_signals": { "concern_level": "moderate", "mentions": ["Asked about scholarships"] },
  "scheduling_constraints": { "constraints": ["Busy weekends"], "preferred_times": ["Weekday afternoons"] },
  "family_context": { "siblings": ["Younger sister age 9"], "decision_makers": ["Spouse not yet on board"] },
  "objections": [{ "topic": "distance", "detail": "30-minute drive", "severity": "low" }],
  "additional_signals": [{ "signal": "referral_source", "detail": "Heard from a friend", "urgency": "low" }],
  "recent_interactions": [...],
  "current_nba": {
    "action": "scheduling_push",
    "channel": "voice",
    "action_brief": {
      "content_directives": [...],
      "overall_tone": "enthusiastic",
      "info_to_prepare": ["available time slots", "what to bring"],
      "things_to_avoid": ["don't casually mention fees"],
      "timing_rationale": "Act quickly while scheduling intent is fresh"
    }
  }
}
```

Context sources:
- `lead_name`, `child_info`, `campaign_goal` → Lead record
- `latest_summary`, `known_facts`, `open_questions` → ContextArtifact table (LLM-derived)
- All enriched dimensions → ContextArtifact table (accumulated across interactions)
- `recent_interactions` → Interaction table (last 5)
- `current_nba` → NBADecision table (includes full action brief)

**Failure mode**: If context assembly fails, a minimal pack with lead name and phone is returned. The agent can still make the call — just with less context.

---

## Deep Dive 2: RL Engine Auditability & Reproducibility

Every NBA decision persists:
1. **The semantic action**: `scheduling_push`, `scholarship_outreach`, etc.
2. **The full action brief**: Content directives, tone, prep, avoids, message draft — everything the agent needs
3. **The RL state**: e.g., `interested:financial_concern`
4. **The Q-value**: The learned value that drove the selection
5. **Signal scores**: Snapshot of all active signals at decision time
6. **Policy inputs**: Full input state for reproducibility

Every Q-table update logs a **StateTransition** record:
- State before and after
- Action taken
- Reward received
- Q-value before and after the update

This enables:
- **Operator inspection**: See why any decision was made and what the RL engine learned from it
- **Offline policy evaluation**: Replay historical transitions to evaluate alternative policies
- **Debugging**: If the engine makes a bad decision, trace exactly which transitions taught it that behavior
- **A/B analysis**: Compare Q-values and outcomes across different state-action pairs

### Hard Overrides (Compliance)

Two states bypass the RL engine entirely:
- `declined` → `stop` (family said no — respect it)
- `opted_out` → `stop` (compliance requirement)

No amount of learning can override these. They are checked before the RL engine runs.

### Action Space Filtering

The RL engine filters the action space per state to prevent nonsensical choices:
- `welcome_onboard` only available for `enrolled` leads
- `retention_check_in` only for `active`/`at_risk`/`inactive`
- `family_engage` only when family context signals exist
- `scholarship_outreach` only when financial signals exist
- `stop` only after 3+ interactions (don't give up immediately)

This constrains exploration to reasonable actions, making UCB exploration more efficient.

---

## Deep Dive 3: Batch SMS Extraction

### Problem

Every individual SMS triggers a full LLM extraction call. A 3-word "sounds good!" doesn't need 10 dimensions extracted. In a rapid back-and-forth thread, the system makes N calls where 1 would suffice — and N-1 intermediate NBA recomputations are wasted since the next outreach won't happen until the thread settles.

### Solution

Each SMS creates an `Interaction` record immediately — one message, one chat bubble in the UI. An `SMSBuffer` row tracks the batch state alongside it. The *LLM extraction* is what gets batched: it's deferred until the thread goes quiet, then runs once on the combined transcript and applies the results to the last interaction in the batch.

**Key principle**: storage is per-message (for display), extraction is per-thread (for cost).

The flush triggers:

| Trigger | Threshold | Rationale |
|---------|-----------|-----------|
| Quiet period | 5 min since last message | Thread has settled, extract the full context |
| Max accumulation | 15 min since first buffered message | Don't defer too long — cap the delay |
| Message count | 6+ unprocessed messages | Long thread, extract before context is stale |
| Urgent keyword | Immediate | Opt-out, sign-up, or scheduling can't wait |

Urgent keywords detected by fast regex scan (no LLM):
- **Opt-out**: stop, unsubscribe, remove me, do not contact
- **Sign-up**: sign up, enroll, register, ready to start
- **Scheduling**: schedule, book, appointment, visit, tour
- **Emergency**: urgent, asap, immediately

### How Flush Works

When a flush is triggered, `flush_sms_thread` collects all unflushed `SMSBuffer` rows for the lead, builds a combined transcript for the LLM, and calls `process_interaction(anchor, transcript_override=combined_transcript)` on the last interaction in the batch. The LLM receives the full conversational thread in one call — better context, better extraction quality, lower cost. The extraction results (intent, sentiment, summary, etc.) are stored on the anchor interaction; all buffer rows are marked as flushed.

### Background Worker: django-q2

Flush scheduling uses django-q2 with the ORM broker (no Redis required):

1. **Per-message task**: When a non-urgent SMS arrives, a `check_sms_flush` task is scheduled for 5 minutes later. The task re-evaluates flush criteria and either flushes or reschedules.
2. **Periodic sweep**: A `flush_stale_threads` task runs every minute as a safety net. It catches any thread that exceeded the 15-minute max accumulation window, covering cases where per-message tasks were lost (worker restart, etc.).
3. **Crash recovery**: On restart, the worker scans `SMSBuffer` for unflushed messages and flushes any stale threads. No messages are lost because the buffer is in the database, not in memory.

### What's Unchanged

- Voice calls and emails still go through `POST /api/interactions/` with immediate extraction
- The original SMS path (`POST /api/interactions/` with `channel="sms"`) still works for callers who want immediate processing (backward compatible)
- The processing pipeline (`process_interaction()`) is identical — `flush_sms_thread` passes a `transcript_override` for the combined thread
- Q-table updates, NBA recomputation, and action briefs work identically

### Trade-off

NBA recomputation is delayed by up to the quiet period (5 min) or max accumulation (15 min) for non-urgent SMS. This is acceptable because the next outreach to this lead is typically hours away. The trade-off is one better extraction from a full thread vs. many worse extractions from fragments.

---

## Risks / What Breaks First

1. **Cold-start Q-table**: With few interactions, the Q-table is mostly seeded priors + UCB exploration. Early decisions may not be optimal. **Mitigation**: Hand-seeded values are conservative and based on proven rule-engine logic. UCB exploration is intelligent (no random actions).

2. **Sparse state visits**: Some (state, action) pairs may rarely be visited, leaving Q-values stale. **Mitigation**: UCB naturally prioritizes under-explored pairs. Monitor `visit_count` to identify cold spots.

3. **Reward function assumptions**: The reward values are hand-tuned. If the real-world value of `interested → trial` isn't 0.7, the RL optimizes for the wrong thing. **Mitigation**: Reward values are configurable constants. Monitor conversion rates vs. RL recommendations to detect misalignment.

4. **LLM extraction quality**: If the LLM misclassifies intent, the state encoding is wrong and the RL learns from incorrect signal. **Mitigation**: Low temperature (0.1), explicit "do not hallucinate" instructions, graceful degradation to `neutral` bucket.

5. **Context bucket information loss**: Bucketing (first-match) means compound signals (financial + objections) are partially lost. **Mitigation**: The action brief enrichment layer adds directives from ALL active signals regardless of bucket. Future improvement: expand state space or use feature-based representation.

6. **Over-contacting leads**: Without robust scheduling enforcement, a bug could trigger too-frequent outreach. **Mitigation**: `wait` is a learned action the RL can choose, hard cooldown logic in action brief timing, max attempts filtering.

---

## File Structure

```
backend/
├── app/
│   ├── models/
│   │   ├── lead.py                # Lead record (parent/child/status)
│   │   ├── interaction.py         # Completed interaction records
│   │   ├── event.py               # Append-only event log
│   │   ├── context_artifact.py    # LLM-derived context (versioned)
│   │   ├── nba_decision.py        # NBA decisions (action brief + RL metadata)
│   │   ├── scheduled_action.py    # Future actions to execute
│   │   ├── q_value.py             # Q-table entries (state, action, value)
│   │   ├── state_transition.py    # RL transition log (audit trail)
│   │   └── sms_buffer.py          # SMS batch staging table
│   ├── services/
│   │   ├── llm_service.py         # LLM extraction (OpenAI + mock)
│   │   ├── context_service.py     # Artifact persistence + context pack assembly
│   │   ├── interaction_processor.py  # Pipeline orchestrator
│   │   ├── nba_engine.py          # NBA entry point (RL + briefs + persistence)
│   │   ├── rl_engine.py           # Q-learning, state encoding, UCB selection
│   │   ├── action_briefs.py       # Semantic action templates + brief builder
│   │   └── sms_batcher.py         # SMS batch buffer, flush logic, background tasks
│   ├── api/                       # REST endpoints
│   ├── management/commands/
│   │   ├── seed_q_table.py        # Seed Q-table with domain priors
│   │   └── setup_sms_sweep.py     # Register periodic SMS flush sweep
│   └── serializers.py             # DRF serializers
├── academy_outreach/              # Django project settings
├── seed_data.py                   # Demo data seeder
└── requirements.txt
```

---

## What I'd Do Next

### Retention: Enrolled-but-not-attending families

The current system handles acquisition well (new → enrolled), but retention is reactive — it only knows what happens during interactions. For families who enroll and don't show up, the system is blind until someone manually logs a check-in. Fixing this requires passive signal feeds:

**Attendance webhook**: When a child checks into class (or misses one), the system receives an event. This triggers state transitions without requiring a manual interaction:
- Enrolled + attended first session → `active`
- Active + missed 2 consecutive sessions → `at_risk`
- At-risk + no attendance for 14 days → `inactive`

These time-based decay rules would run as a background job, scanning for attendance gaps and auto-transitioning statuses. Each transition feeds the Q-table just like interaction-driven transitions — the RL learns which actions prevent drop-off.

**Payment signals**: Missed or late payments are strong leading indicators of churn. A payment webhook would:
- Successful payment → no action (positive signal, reinforce current state)
- Late payment → add `payment_concern` context signal (similar to `financial_concern`)
- Missed payment → transition to `at_risk` if currently `active`

Payment signals would feed into the context bucket and enrich action briefs — e.g., a retention check-in call brief would include "don't mention the missed payment directly; ask if everything is going well and if the family needs any support."

**New semantic actions for retention**: The current `retention_check_in` is too generic. With attendance data, we'd add:
- `first_session_reminder`: The highest-leverage message — the #1 drop-off is between enrollment and first class
- `reschedule_offer`: They missed their slot, offer a new one without guilt
- `barrier_investigation`: Probing call to understand WHY (transport? child lost interest? schedule conflict?)
- `social_proof`: Share photos/stories from other families to rebuild excitement
- `low_commitment_invite`: "Come to our free open house" is easier than "come to class"
- `win_back_offer`: For 30+ day inactive families, a compelling reason to return

These would expand the action space from 12 to ~18 semantic actions, adding ~720 Q-table entries for retention-specific state-action pairs.

### Action Reminders

The NBA banner suggests what to do next, but many suggestions include a timing component ("follow up in 2 days," "call next Tuesday"). Today the operator has to remember this themselves or mentally track it. A reminder system closes this gap:

**How it works**: The operator clicks "Set reminder" on any NBA suggestion. They pick a time (quick presets like "Tomorrow 9am," "In 2 days," "Next Monday," or a custom datetime). The system creates a `ScheduledReminder` tied to the lead and the NBA decision. When the reminder fires, the operator sees a notification (in-app badge, browser notification, or both) that resurfaces the lead and the original suggestion.

**Model**:
```
ScheduledReminder
  - lead (FK)
  - nba_decision (FK, nullable)
  - remind_at (datetime)
  - note (text, optional — operator can add context)
  - dismissed (bool)
  - created_at
```

**Auto-reminders from NBA timing**: When the RL engine produces an action brief with a `scheduled_for` time (e.g., "follow up in 48 hours"), the system can auto-create a reminder without the operator clicking anything. The operator sees it in their reminder queue and can snooze, dismiss, or act on it. This bridges the gap between the RL engine's timing recommendations and the operator's actual workflow.

**Reminder queue**: A dedicated sidebar section or top-level view showing all upcoming reminders across leads, sorted by time. Overdue reminders are highlighted. Clicking a reminder navigates directly to the lead's conversation with the original NBA context restored.

**RL feedback loop**: When an operator acts on a reminder (sends a message, makes a call), the action is attributed to the original NBA decision that spawned it. This lets the Q-table learn whether time-delayed actions are effective — if "follow up in 2 days" consistently leads to better outcomes than "follow up immediately," the RL learns to prefer delayed timing.

### Batch RL Updates (Daily Training)

The current system updates the Q-table synchronously inside `process_interaction` — every interaction triggers an immediate TD-learning step. This is fine for a demo and for low volume, but doesn't scale. At companies processing thousands of interactions daily, real-time Q-updates create several problems:

- **Write contention**: Concurrent interactions for different leads can race on shared Q-table rows (same state-action pairs), causing lost updates or requiring row-level locks that serialize throughput.
- **Noisy single-step updates**: One interaction moves the Q-value by `alpha * td_error`. With high volume, the Q-table bounces around from individual noisy signals rather than learning from stable aggregate patterns.
- **Coupling pipeline latency to RL**: The API response time includes the Q-update, which adds database writes. At scale, this latency compounds.

**The standard at scale: batch offline training.** Instead of updating Q-values inline, the system would:

1. **Log transitions only**: During `process_interaction`, record the `(state_before, action, reward, state_after)` tuple to the `StateTransition` table (we already do this). Skip the `update_q_table` call entirely.

2. **Daily batch job**: A scheduled job (e.g., nightly at 2am via cron or django-q Schedule) reads all new transitions since the last training run and performs batch Q-learning:
   ```
   for each transition in today's batch:
       td_error = reward + gamma * max_a Q(s', a) - Q(s, a)
       Q(s, a) += alpha * td_error
   ```
   This can run multiple epochs over the batch for more stable convergence. The batch size also enables techniques like experience replay (sampling uniformly from a replay buffer rather than processing chronologically).

3. **Snapshot and promote**: After training, snapshot the Q-table as a versioned checkpoint. Promote it to "active" only after validation (e.g., compare average Q-values against the previous version, flag anomalies). The serving layer reads from the active snapshot.

4. **Serving stays fast**: `compute_nba` reads Q-values from the active snapshot (read-only, cacheable). No writes during request handling. This decouples serving latency from training entirely.

**Why this matters**: Real-time updates conflate the serving path (fast, read-heavy) with the training path (slow, write-heavy). Batch training separates these concerns cleanly. It also enables more sophisticated training — prioritized experience replay, eligibility traces, or even upgrading from tabular Q-learning to a function approximator (neural net) without touching the serving code.

**Migration path**: The current `StateTransition` table already logs everything the batch job needs. The change is purely about *when* `update_q_table` runs — moving it from inline to a scheduled job. The `QValue` table structure stays the same. This is a configuration change, not an architectural one.

### Other improvements

1. **Outcome tracking dashboard**: Visualize Q-value evolution, reward distribution, and state transition patterns to monitor RL health
2. **Operator overrides**: Let operators reject an NBA with a reason; feed rejections back as negative reward
3. **A/B testing framework**: Run the seeded Q-table vs. a learning Q-table side by side and compare conversion rates
4. **Feature-based state representation**: Replace discrete buckets with continuous feature vectors for richer state encoding (requires function approximation — linear or shallow neural net)
5. **Multi-step action plans**: Instead of one action, produce a planned sequence (e.g., "SMS now, call in 24h, check-in in 72h") with a learned policy over the sequence
6. **Real OpenAI integration testing**: Validate extraction quality and RL advisor prompts across diverse transcript samples
7. **Test suite**: Unit tests for state encoding, Q-updates, action filtering, and brief generation. Integration tests for the full pipeline.

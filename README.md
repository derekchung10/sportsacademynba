# Academy Outreach Platform

An autonomous outreach platform for sports academies that learns optimal engagement strategies from interaction outcomes using graph reinforcement learning. Produces rich action briefs — not just "send an SMS," but what to say, what tone to use, what to prepare, and what to avoid.

## Quick Start

```bash
# ─── Backend ─────────────────────────────────────────────
cd backend

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate          # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure (mock LLM works out of the box — no API key needed)
cp .env.example .env

# Run migrations
python manage.py migrate

# Seed RL Q-table with domain priors
python manage.py seed_q_table

# Register periodic SMS batch flush task
python manage.py setup_sms_sweep

# Seed demo data (leads + interactions)
python seed_data.py

# Start server on port 8001
python manage.py runserver 8001

# (Optional) Start background worker for SMS batch flushing
python manage.py qcluster

# ─── Frontend ────────────────────────────────────────────
cd ../frontend
npm install
npm run dev          # Starts Vite dev server on port 5174
```

**Open in browser:**
- Dashboard: http://localhost:5174

## How It Works

1. **Interaction arrives** (completed call/SMS/email)
2. **LLM extracts** structured signals: intent, sentiment, financial concerns, objections, family context, scheduling constraints, and open-ended signals the system didn't anticipate
3. **Context artifacts** are persisted and accumulated across interactions
4. **Q-table updates**: the previous action is rewarded or penalized based on whether the lead progressed in the funnel
5. **RL engine selects** the best semantic action (e.g., `scholarship_outreach`, `warm_follow_up`) for the current state using UCB exploration
6. **Action brief is built**: content directives, tone, info to prepare, things to avoid, timing rationale, and a message draft — enriched with all active context signals

## Features

- **Graph RL Decisioning**: Q-learning over ~90 discrete states × 12 semantic actions. Learns which outreach strategies drive conversions — not just the next best action, but the best trajectory.
- **Rich Action Briefs**: Every NBA decision includes what to say, what tone to use, what materials to have ready, what to avoid, and a message draft for SMS/email.
- **LLM Extraction**: Summary, facts, intent, sentiment, financial signals, scheduling constraints, family context, objections, and open-ended signals — all from a single extraction call.
- **Batch SMS Extraction**: Individual SMS messages buffer in a staging table and flush as a single thread when the conversation goes quiet (5 min), hits max accumulation (15 min), or reaches 6+ messages. Urgent keywords (opt-out, sign-up, scheduling) trigger immediate flush.
- **Open-Ended Signal Detection**: The LLM captures signals outside the fixed schema (life events, competitive offers, special needs, referral sources) so the system handles situations you didn't anticipate.
- **Context Injection Boundary**: Assembled context packs for outbound/inbound calls with full action brief.
- **Outcome-Adaptive Learning**: Q-values update from real outcomes. Actions that lead to progression are reinforced; actions that lead to regression are penalized.
- **Full Auditability**: Every decision stores the RL state, Q-value, signal context, and policy inputs. Every Q-update logs a state transition with reward and Q-value change.
- **Operator Dashboard**: Search, filter, inspect lead timelines, interactions, context, and NBA history.
- **Event Sourcing**: Append-only event log for full timeline reconstruction.

## Architecture

See [DESIGN.md](DESIGN.md) for detailed architecture, trade-offs, RL design decisions, and deep dives.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/leads/` | List/search/filter leads |
| `POST` | `/api/leads/` | Create a new lead |
| `GET` | `/api/leads/<id>` | Full lead detail (timeline, context, NBA) |
| `GET` | `/api/leads/stats` | Dashboard aggregate stats |
| `POST` | `/api/interactions/` | Submit completed interaction (triggers full pipeline) |
| `POST` | `/api/interactions/sms` | Buffer a single SMS message for batch extraction |
| `GET` | `/api/interactions/<id>` | Get interaction with LLM-derived fields |
| `GET` | `/api/context/<id>/pack` | Assembled context pack |
| `GET` | `/api/context/<id>/prepare-outbound-call` | Context injection for outbound calls |
| `GET` | `/api/context/<id>/prepare-inbound-call` | Context injection for inbound calls |
| `GET` | `/api/nba/<id>/current` | Current NBA decision (includes full action brief) |
| `GET` | `/api/nba/<id>/history` | NBA decision history |
| `POST` | `/api/nba/<id>/recompute` | Force recompute NBA via RL engine |

## Tech Stack

- **Backend**: Python 3.12, Django 5.x, Django REST Framework
- **Task Queue**: django-q2 (ORM broker — no Redis needed)
- **Database**: SQLite (dev) / PostgreSQL (production)
- **LLM**: OpenAI gpt-4o-mini (with mock fallback for zero-cost development)
- **RL**: Tabular Q-learning with UCB exploration, ~1,080 state-action pairs
- **Frontend**: React 18 + Tailwind CSS (Vite dev server)

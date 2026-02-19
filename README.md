# Academy Outreach Platform

An autonomous outreach platform for sports academies that learns from prior interactions, produces Next Best Action decisions, and provides an operator dashboard for inspection.

## Quick Start

```bash
cd backend

# Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows PowerShell
# source .venv/bin/activate         # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure
copy env.example .env
# Edit .env with your PostgreSQL credentials

# Create the PostgreSQL database
# (make sure PostgreSQL is running)
createdb academy_outreach
# Or via psql: CREATE DATABASE academy_outreach;

# Run migrations
python manage.py migrate

# Seed demo data (6 leads, 8 interactions)
python seed_data.py

# Start server
python manage.py runserver
```

**Open in browser:**
- Dashboard: http://localhost:8000
- API Docs: Use the API endpoints below (no auto-docs like Swagger by default; add `drf-spectacular` for that)

## Features

- **Interaction Processing Pipeline**: Submit a completed call/SMS, system extracts insights via LLM, updates lead state, produces NBA
- **LLM Extraction**: Summary, facts, intent, sentiment, open questions from transcripts (mock or OpenAI)
- **Next Best Action Engine**: Deterministic rule-based decisioning with full audit trail
- **Context Injection Boundary**: Assembled context packs for outbound/inbound calls
- **Operator Dashboard**: Search, filter, inspect lead timelines, interactions, context, and NBA history
- **Event Sourcing**: Append-only event log for full timeline reconstruction

## Architecture

See [DESIGN.md](DESIGN.md) for detailed architecture, assumptions, trade-offs, and deep dives.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/leads/` | List/search/filter leads |
| `POST` | `/api/leads/` | Create a new lead |
| `GET` | `/api/leads/<id>` | Full lead detail (timeline, context, NBA) |
| `GET` | `/api/leads/stats` | Dashboard aggregate stats |
| `POST` | `/api/interactions/` | Submit completed interaction (triggers pipeline) |
| `GET` | `/api/interactions/<id>` | Get interaction with LLM-derived fields |
| `GET` | `/api/context/<id>/pack` | Assembled context pack |
| `GET` | `/api/context/<id>/prepare-outbound-call` | Context injection for outbound calls |
| `GET` | `/api/context/<id>/prepare-inbound-call` | Context injection for inbound calls |
| `GET` | `/api/nba/<id>/current` | Current NBA decision |
| `GET` | `/api/nba/<id>/history` | NBA decision history |
| `POST` | `/api/nba/<id>/recompute` | Force recompute NBA |

## Tech Stack

- **Backend**: Python 3.11+, Django 5.x, Django REST Framework, PostgreSQL
- **LLM**: OpenAI gpt-4o-mini (with mock fallback)
- **Frontend**: Alpine.js + Tailwind CSS (served by Django, zero Node.js dependency)

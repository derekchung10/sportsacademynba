# Stealth: Take-Home Challenge

## Autonomous Agent Platform: Context Enrichment + Next Best Action + Operator Experience

**Target timebox:** ~5–6 hours of focused work.  
**Start from a blank repo** (no starter code).  
**Primary channels:** voice, SMS (email is an optional extension).

You may mock external providers. Bonus points for real sandbox integrations.

---

## 1) The Goal

Build a small but realistic slice of an **autonomous outreach platform** for sports academies that:

1. **Learns from prior touchpoints** so future interactions can pick up where the last one left off.
2. Produces a **Next Best Action (NBA)** after each interaction completes.
3. (Bonus points) Provides an **operator experience/UI** that makes the system’s state and decisions easy to inspect.

This challenge is intentionally open-ended. We want to see your judgment in:

- system boundaries and interface/API design,
- data modeling,
- cost-conscious LLM usage,
- pragmatic trade-offs under time constraints.

Document assumptions and decisions in your README.

### Show your thinking (required)

We intentionally haven’t specified constraints or tradeoffs. We're looking for you to choose reasonable assumptions, call out tradeoffs/limitations in your approach, and make your reasoning explicit.

In your README (or a short DESIGN.md), include:

- **Assumptions:** what you assumed about inputs, traffic, reliability, and operational context.
- **Decisions & trade-offs:** what you chose, what you intentionally didn’t build, and key alternatives you considered.
- **Risks / what breaks first:** your top risks and how you’d mitigate them.
- **Two deep dives:** pick **two** concerns you think matter most and go deeper.
  You can do this via design + a small proof/harness/tests, or a concrete design with interfaces and failure modes.
  Explain why you picked them.

When we meet in person, we can also talk through one approach you considered and rejected (i.e., what you didn’t choose and why) and one failure mode you were able to identify an handle that would've been dangerous for the system.

---

## 2) What You Should Build

You are free to choose **how** you implement this (REST, GraphQL, event-driven, CLI scripts, in-app simulator, etc.).  
What matters is that your system clearly demonstrates the capabilities below.

### Minimum viable submission (what “done” looks like)

Your submission should, at minimum:

- take a lead, and decide the next best action for them given a goal for that lead, and the history of interactions with that lead
- persist enough history/state to answer: what happened, what we know, what we’ll do next (and why)
- choose the next best "channel" for that lead (between voice and sms with email being optionally implemented)
- provide a way to inspect the lead timeline + decisions (CLI is fine)
- update the next best action upon new interactions/events with that lead

### 2.1 State & history that make the system explainable

Demonstrate **whatever persisted (or reproducible) representation you believe is necessary** so that a reviewer/operator can:

- reconstruct a lead’s interaction timeline (“what happened?”),
- understand the current lead state/context (“what do we know?”),
- see the recommended next action (or “no action”) and the reasoning behind it (“what happens next, and why?”),
- reproduce decisions from stored inputs (or clearly explain what is non-reproducible and why).

How you model this is up to you:

- event log vs snapshots/materialized views (or both),
- source-of-truth vs derived artifacts,
- what you persist vs compute on demand.

Include a brief note in your README about these choices and the trade-offs.

### 2.2 An “interaction completed” entrypoint

Provide a way to submit a completed interaction and trigger downstream processing.

How you orchestrate processing is up to you (sync vs async, jobs, events, etc.). What we need to see is that submitting an interaction leads to **observable outcomes** in your system, such as:

- updated history/state for the lead,
- any derived signals you choose to produce (summaries, structured facts, intents, tags, etc.),
- an updated “next action” recommendation (or “no action”) with an explanation,
- if you schedule work for later, a clear representation of that intent (even if execution is stubbed).

Include a simple way for us to exercise your system (seed data, sample payloads, replay script, or simulator).

### 2.3 LLM usage for summarization / extraction

Use an LLM to derive useful information from interactions (summary, structured facts, intent, open questions—your choice).

We care about:

- usefulness of what you extract,
- prompt quality and output handling,
- cost-control strategy (explain in README).

### 2.4 Context enrichment & “injection” boundary

Demonstrate how prior context would be made available **before**:

- an outbound call is placed, and
- an inbound call is answered.

This can be a real integration or a stubbed boundary (e.g., a fake “voice provider client” that requests a context pack before placing/answering a call). What we need to see is:

- what context is assembled,
- where it comes from,
- how it would be attached/loaded at call time.

### 2.5 Next Best Action (NBA) decisioning

After each completed interaction, produce a “what happens next?” decision and make the decision + rationale **inspectable** (persist it, derive it from stored inputs, or otherwise make it easy to review).

Design your own rules/policy shape. We’re looking for:

- clarity and defensibility (why these rules?),
- determinism (same inputs → same outputs),
- sensible updates to any campaign/sequence state you model.

#### Scheduling (if applicable)

If you choose actions that occur later, show how you would represent and execute that schedule in a way that’s inspectable (persistence, a queue, an in-memory scheduler, etc.—your choice), even if execution is stubbed.

The flow should look something like:

1. The agent reaches out
2. The parent does/does not respond
3. The agent decides what the "next best action" should be as well as the "next best channel"
4. Ideally, there should be some way for the agent to validate or invalidate its decision with subsequent data
5. (Optional) All of this flow is visualized in a UI/UX

---

## 3) Operator Experience (Bonus)

(If time allows) Provide an operator experience that helps a non-technical user answer:

- **What happened?**
- **What do we know?**
- **What will we do next, and why?**

This can be a web UI, CLI, local dashboard, or another approach—choose what you think best demonstrates the system.

We value:

- ability to quickly find a lead and inspect its state,
- at least some basic filtering/search that you think an operator would actually need.
- bonus points for creating insights that are visible and compelling in the app
- bonus points for a best-in-class UI/UX

---

## 4) Extensions

For SMS (and email if you choose to implement it), treat them as first-class interaction types:

- they can update context,
- they can influence NBA decisions,
- they are visible in the operator experience.

---

## 5) Deliverables

Submit:

1. Repo link (or zip)
2. README (or DESIGN.md) that covers:
   - how to run / demo
   - your **assumptions** (what constraints you assumed and why)
   - system overview: components, boundaries, and key interfaces
   - how interaction history becomes a durable **context artifact** and how that context is used for future interactions
   - your NBA approach (policy shape, rationale, and how you keep it testable)
   - how you use LLMs (prompts/outputs) and what you did to keep usage pragmatic
   - **two deep dives** (what you chose to go deep on, and why)
   - what you’d do with one more day
3. (Hint) a short demo script or seeded sample data can help you start thinking about what the data should look like and test your system

---

## 6) Evaluation Criteria

We’ll evaluate:

- **Judgment & design:** good boundaries, sensible abstractions, appropriate trade-offs
- **Robustness:** safe processing, clear error handling
- **Product sense:** outreach heuristics that feel realistic
- **LLM pragmatism:** cost control + sane prompts/output handling
- **Operator experience:** understandable and helpful
- **Clarity:** strong README and readable code

### Glossary (quick definitions)

- **Lead:** a parent who a business wants to talk to
- **Interaction:** a completed voice call or SMS thread (feel free to choose how you want to represent this).
- **NBA (Next Best Action):** what to do next (channel + action + optional schedule) plus rationale.
- **Operator:** a non-technical user who needs to inspect what happened and what happens next.

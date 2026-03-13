# Model Evaluation: Strategic Protocol & Platform Decision

Three models (GPT-5.4, Codex, O3) were asked the same two questions about our O1 usage. Their answers were synthesized by Claude Opus 4.6 into the upgraded protocol and system prompt.

## Questions Asked

1. **Protocol:** Are we framing our questions to the strategic reasoning tier in a way that maximally exploits chain-of-thought reasoning? What are we missing?
2. **Platform:** Should we build a dedicated O1-based Assistant on OpenAI's platform, or stick with raw API + our own pgvector + RRF retrieval?

## Responses

| File | Model | Question |
|------|-------|----------|
| `gpt54-q1-protocol.md` | GPT-5.4 | Q1: Protocol gaps |
| `o3-q1-protocol.md` | O3 | Q1: Protocol gaps + schema delta |
| `codex-q2-platform.md` | Codex | Q2: Platform decision |
| `o3-q2-platform.md` | O3 | Q2: Platform decision |

## Verdict

- **Q1:** Protocol upgraded from 6-part to 12-part contract (see `o1_next_question_v2.md`)
- **Q2:** Unanimous — local-first with raw API. Assistants API is optional convenience, not capability.

## Model Performance

| Model | Strength | Weakness |
|-------|----------|----------|
| O3 | Drop-in schema, operational precision | N/A |
| Codex | Clean, direct, no ego | Less depth |
| GPT-5.4 | Best conceptual analysis | Self-promoted as O1's replacement |

# Next Session — Speculative Decoding + Heuristic Extraction

## Where We Left Off

Goal 001 is **COMPLETE**. The lab architecture is validated:
- 14B coder scored 24/25 (winner), matching draftbench predictions
- Full report: `ai-lab/goal_001_results/GOAL_001_REPORT.md`
- V-Model is at "Extract learnings, update heuristics"

## Next: Two Parallel Tracks

### Track A: MLX Speculative Decoding Test

The draftbench data predicts **50-80% speedup** with 14B + 1.5B draft on Apple Silicon.
Ollama doesn't support speculative decoding natively — need to use MLX or llama.cpp.

```bash
# Install mlx-lm if not present
pip install mlx-lm

# Test 14B + 1.5B draft pairing
# (specific commands depend on MLX model format — research needed)
```

**What to validate:**
- Does the speedup match draftbench predictions (~50-80%)?
- Does quality remain comparable to standalone 14B?
- Is the memory footprint ~13GB (14B + 1.5B), leaving headroom for critic?

### Track B: Extract Heuristics → V-Model Ascent

The V-Model needs to climb back up:
1. **Extract learnings** into skills DB (not just "14B wins" but the principles)
2. **Confirm architecture** — write the closing V-Model assessment

Learnings to codify:
- Model family > parameter count for targeted tasks
- Critic JSON parsing must handle markdown fences
- Benchmark suite (5 tasks, 5 criteria, critic-scored) is effective
- gpt-4o as critic is reliable but needs robust response parsing

### On Deck (not blocking these)
- Extract GPT-5.4's eval harness into `ai-lab/evals/knowledge_plane/`
- Build the A/B retrieval comparison (local vs hosted)
- Add vector search to skills DB

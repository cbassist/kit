# Next Session — Goal 001 Smoke Test

## Pre-flight (after reboot)

1. **Open Terminal only** — no Cursor, no Claude desktop, no Docker
2. Verify Ollama is running:
   ```bash
   ollama list
   ```
3. Check memory headroom:
   ```bash
   memory_pressure | head -5
   ```
   Want to see ~14GB+ free (should be easy with just Terminal + Ollama)

## Run the smoke test

```bash
cd /Users/mike/projects/01/ai-lab
uv run run_goal_001.py
```

This tests the two already-installed models:
- `qwen2.5-coder:14b-instruct-q6_K` (~12GB) — should score well
- `llama3.2:1b` (~1.3GB) — baseline, should score low

**What to look for:**
- 14B should clearly outscore 1B (validates the benchmark differentiates quality)
- No crashes, no OOM
- Results saved to `ai-lab/goal_001_results/`
- Winner recorded in `ai-lab/skills.json`

## If smoke test passes → full sweep

```bash
# Pull additional models
ollama pull qwen2.5:1.5b
ollama pull qwen2.5:7b

# Run full sweep
uv run run_goal_001.py --full
```

## If something breaks

- **OOM on 14B**: Model needs ~12GB, may not fit if system is using too much. Try `--model llama3.2:1b` first to validate the harness, then close apps.
- **API errors**: Check that `OPENAI_API_KEY` is set in environment (the critic uses gpt-4o via API)
- **Ollama not responding**: `ollama serve` in a separate terminal tab

## What this validates

If the 14B model scores significantly higher than 1B, and the harness runs clean:
- Benchmark suite produces differentiated, meaningful scores ✓
- Critic tier (gpt-4o) reliably scores model output ✓
- Results persist correctly ✓
- Skills DB records the winner ✓
- We're ready for the convergence test with draft model pairings

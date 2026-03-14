"""
config.py — Central configuration for the AI Lab system.

All model names, timeouts, and feature flags live here.
Reads from a .env file (or environment variables) via python-dotenv.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env from the project root (one level up from ai-lab/) ──
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=False)


# ════════════════════════════════════════════════════════════════
#  API Keys
# ════════════════════════════════════════════════════════════════

OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")

if not OPENAI_API_KEY:
    raise EnvironmentError(
        "OPENAI_API_KEY is not set. "
        "Copy .env.example → .env and add your key."
    )


# ════════════════════════════════════════════════════════════════
#  Model Routing
#  These map each cognitive loop to its designated model.
# ════════════════════════════════════════════════════════════════

class Models:
    """
    Three-tier model stack matching the system architecture.

      STRATEGIC  → OpenAI o1 (deep reasoning, expensive, called rarely)
      PROJECT    → Mid-tier model (review, routing, batch evaluation)
      WORKER     → Fast/cheap model or local Ollama model (execution loop)
    """
    STRATEGIC: str = os.environ.get("STRATEGIC_MODEL", "o1")
    PROJECT: str   = os.environ.get("PROJECT_MODEL",   "gpt-4o")
    WORKER: str    = os.environ.get("WORKER_MODEL",    "gpt-4o-mini")

    # Local Ollama override (used when OLLAMA_BASE_URL is set)
    OLLAMA_BASE_URL: str  = os.environ.get("OLLAMA_BASE_URL", "")
    LOCAL_WORKER: str     = os.environ.get("LOCAL_WORKER_MODEL", "llama3")


# ════════════════════════════════════════════════════════════════
#  o1-Specific Settings
#  o1 uses `max_completion_tokens` instead of `max_tokens`,
#  does not accept a `temperature` param (fixed at 1),
#  and does not support streaming.
# ════════════════════════════════════════════════════════════════

class O1Settings:
    MAX_COMPLETION_TOKENS: int = int(os.environ.get("O1_MAX_TOKENS", "8000"))
    # reasoning_effort: "low" | "medium" | "high"
    REASONING_EFFORT: str = os.environ.get("O1_REASONING_EFFORT", "high")
    # v2 contract: if strategist confidence < this, output experiment not plan
    CONFIDENCE_THRESHOLD: float = float(os.environ.get("O1_CONFIDENCE_THRESHOLD", "0.75"))


# ════════════════════════════════════════════════════════════════
#  System Loop Thresholds
# ════════════════════════════════════════════════════════════════

class Thresholds:
    # How many worker failures before escalating to o1 for diagnosis
    ESCALATE_TO_STRATEGIC_AFTER: int = int(
        os.environ.get("ESCALATE_THRESHOLD", "5")
    )
    # Max experiments per project loop iteration
    MAX_EXPERIMENTS_PER_CYCLE: int = int(
        os.environ.get("MAX_EXPERIMENTS", "20")
    )
    # Hard safety cap to prevent infinite orchestration loops
    MAX_PROJECT_ITERATIONS: int = int(
        os.environ.get("MAX_PROJECT_ITERATIONS", "200")
    )
    # Prevent endless strategic replans for one stuck task
    MAX_STRATEGIC_REPLANS_PER_TASK: int = int(
        os.environ.get("MAX_STRATEGIC_REPLANS_PER_TASK", "3")
    )


# ════════════════════════════════════════════════════════════════
#  Paths
# ════════════════════════════════════════════════════════════════

class Paths:
    ROOT         = Path(__file__).parent
    ARTIFACTS    = ROOT / "artifacts"
    STATE_DB     = ROOT / "state.db"
    SKILLS_DB    = ROOT / "skills.json"
    HEURISTICS_DB = ROOT / "heuristics.json"
    EPISODIC_DB  = ROOT / "episodic.json"

    @classmethod
    def ensure_dirs(cls):
        cls.ARTIFACTS.mkdir(parents=True, exist_ok=True)

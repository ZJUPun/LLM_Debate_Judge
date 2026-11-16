"""Central settings. Change things here (or via environment variables), not inside the code."""
import os

# --- Model / API -------------------------------------------------------------
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")          # the assignment requires deepseek-flash
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
API_KEY_ENV = "DEEPSEEK_API_KEY"                               # export DEEPSEEK_API_KEY=sk-...

DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 2048
REQUEST_TIMEOUT = 120      # seconds
MAX_RETRIES = 5

# --- Prices (US$ per 1 million tokens) ---------------------------------------
# !! CHECK THESE against https://api-docs.deepseek.com/quick_start/pricing before your runs.
# DeepSeek splits input into cache-hit and cache-miss tokens. Reasoning ("thinking") tokens
# are billed as output. Peak/off-peak rates may differ; use the rate you will actually pay.
PRICE_PER_M = {
    "input_cache_miss": float(os.getenv("PRICE_IN_MISS", "0.30")),
    "input_cache_hit": float(os.getenv("PRICE_IN_HIT", "0.006")),
    "output": float(os.getenv("PRICE_OUT", "1.20")),
}

# --- Budget ------------------------------------------------------------------
# The course limit is US$30 per team. The harness stops a run if the *real* money spent
# in that run passes --budget (default below). Cached calls cost nothing.
DEFAULT_RUN_BUDGET_USD = float(os.getenv("DJ_RUN_BUDGET", "10"))

# --- Paths -------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(ROOT, "cache", "llm_cache.sqlite")
# One log file per team member, so two people never edit the same file (no Git conflicts).
DJ_USER = os.getenv("DJ_USER") or os.getenv("USER") or os.getenv("USERNAME") or "me"
CALL_LOG_PATH = os.path.join(ROOT, "logs", f"calls_{DJ_USER}.jsonl")
SAMPLE_DATA_DIR = os.path.join(ROOT, "data", "samples")

# --- Offline test mode -------------------------------------------------------
# DJ_MOCK=1 replaces the API with a fake model so you can test the pipeline for free.
MOCK = os.getenv("DJ_MOCK", "0") == "1"

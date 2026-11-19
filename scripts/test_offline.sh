#!/usr/bin/env bash
# Free end-to-end test with a FAKE model (no API key, no internet, no cost).
# The accuracies are meaningless; this only checks that the pipeline works.
set -euo pipefail
cd "$(dirname "$0")/.."
export DJ_MOCK=1
# Some fake calls simulate hitting max_tokens (finish_reason == "length") so the
# truncation tracking and the outcome breakdown are exercised too.
export DJ_MOCK_TRUNCATION_RATE="${DJ_MOCK_TRUNCATION_RATE:-0.3}"
python -m dj.run --dataset sample_math --out results/_mock_math \
  --methods cot "sc:k=3" "sc:k=9" "debate:n=3,r=2" "debate:n=3,r=2,agg=judge,stop=1"
python -m dj.run --dataset sample_mc --out results/_mock_mc --methods cot "sc:k=5" "debate:n=3,r=1"
python -m dj.run --dataset sample_pair --out results/_mock_pair --methods judge "judge:k=3"
# Structural check: every fresh record must carry the v2 metrics fields.
python - <<'PY'
import glob, json, sys
need = {"outcome", "truncated_calls", "calls_made", "metrics_version"}
seen_trunc = False
for path in glob.glob("results/_mock_*/records/*.jsonl"):
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        missing = need - set(r)
        assert not missing, f"{path}: missing {missing}"
        assert r["outcome"] in ("correct", "wrong", "no_answer", "truncated", "technical_error")
        seen_trunc |= bool(r.get("truncated_calls"))
assert seen_trunc, "mock never produced a truncated call - truncation tracking is broken"
print("record schema + truncation tracking OK")
PY
echo "OFFLINE TEST OK"

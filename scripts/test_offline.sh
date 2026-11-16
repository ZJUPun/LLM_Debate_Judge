#!/usr/bin/env bash
# Free end-to-end test with a FAKE model (no API key, no internet, no cost).
# The accuracies are meaningless; this only checks that the pipeline works.
set -euo pipefail
cd "$(dirname "$0")/.."
export DJ_MOCK=1
python -m dj.run --dataset sample_math --out results/_mock_math \
  --methods cot "sc:k=3" "sc:k=9" "debate:n=3,r=2" "debate:n=3,r=2,agg=judge,stop=1"
python -m dj.run --dataset sample_mc --out results/_mock_mc --methods cot "sc:k=5" "debate:n=3,r=1"
python -m dj.run --dataset sample_pair --out results/_mock_pair --methods judge "judge:k=3"
echo "OFFLINE TEST OK"

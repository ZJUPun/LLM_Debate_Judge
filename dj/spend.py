"""How much real money has the team spent so far? Sums every logs/calls_*.jsonl
(one file per team member - commit them so the total covers both of you).

  python -m dj.spend
"""
import glob
import json
import os
from collections import defaultdict

from . import config


def main():
    suffix = ".mock" if config.MOCK else ""
    paths = sorted(glob.glob(os.path.join(config.ROOT, "logs", f"calls_*.jsonl{suffix}")))
    if not config.MOCK:
        paths = [p for p in paths if not p.endswith(".mock")]
    if not paths:
        print("No calls logged yet.")
        return
    grand = 0.0
    for path in paths:
        total, calls, by_kind = 0.0, 0, defaultdict(float)
        with open(path, encoding="utf-8") as f:
            for line in f:
                e = json.loads(line)
                total += e["cost_usd"]
                calls += 1
                by_kind[e["tag"].split("/")[0] or "untagged"] += e["cost_usd"]
        grand += total
        print(f"{os.path.basename(path)}: {calls} paid calls, ${total:.3f}")
        for k, v in sorted(by_kind.items(), key=lambda t: -t[1]):
            print(f"    {k:<15} ${v:.3f}")
    print(f"TEAM TOTAL ${grand:.3f} of the $30 limit")


if __name__ == "__main__":
    main()

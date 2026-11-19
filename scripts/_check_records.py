import glob, json

need = {"outcome", "truncated_calls", "calls_made", "metrics_version"}
seen_trunc = False
files = recs = 0
for path in glob.glob("results/_mock_math/records/*.jsonl") + \
            glob.glob("results/_mock_mc/records/*.jsonl") + \
            glob.glob("results/_mock_pair/records/*.jsonl"):
    files += 1
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        recs += 1
        missing = need - set(r)
        assert not missing, f"{path}: missing {missing}"
        assert r["outcome"] in ("correct", "wrong", "no_answer", "truncated", "technical_error")
        seen_trunc |= bool(r.get("truncated_calls"))
assert seen_trunc, "mock never produced a truncated call - truncation tracking is broken"
print("record schema + truncation tracking OK |", files, "files,", recs, "records")

# Instructions for coding agents (Claude Code, Cursor, Codex, ...)

1. Read `NOTES.md` and `README.md` before doing anything. They hold the current project state.
2. At the end of a session, update `NOTES.md` (status, results, decisions, session log).
3. Every API call goes through `dj.llm.chat()`. Never create another OpenAI client:
   it would bypass cost tracking, the cache and the logs.
4. New methods go in `dj/methods.py` with `@register(...)`. Do not change the baselines,
   the answer extraction or the stats without writing the reason in `NOTES.md`
   (it would make old results incomparable).
5. Test with `bash scripts/test_offline.sh` (free) before any real run. Ask the user before
   any run that could cost more than $1.
6. Never commit API keys. The team limit is $30 in total.
7. The report text is written by the students, not by an AI tool (course rule). You may help
   with code, tables and plots only.

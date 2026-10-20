# Before sharing

- Review the actual git ls-files --cached --others --exclude-standard list, including already-tracked ignored files.
- Run python3 -m uv run python scripts/check_public_safety.py. It prints filenames/categories, not matching values. A clean heuristic scan is not a secrecy guarantee.
- Keep .env, credential references, raw Reddit bodies, author metadata, provider responses, prices, caches and all runs local/ignored.
- Public examples must be intentionally selected: metrics/charts, source links and minimal excerpts only. Review HTML embedded assets and JSON specs too. Do not imply redistribution rights for Reddit or market datasets.
- Check every actual model ID, hypothesis label, source-text version caveat, cost assumption and failed/excluded candidate.
- Never describe development-used data as untouched or a hypothesis as a faithful reproduction. Do not promote a best historical result as an edge.
- Do not push, publish, deploy or send messages without explicit user instruction. This project has not been published.

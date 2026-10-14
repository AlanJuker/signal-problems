# 2. Resolving free-text station names

Date: 2026-10-14
Status: Accepted

## Context

The `Station` column of the TTC delay log is typed by hand into a field limited to 22 characters. The
2025–2026 data has 1,251 distinct values for 70 stations: per-line platform names (`BLOOR STATION` and
`YONGE BD STATION` are both Bloor–Yonge), stations renamed while the log was being written (`DUNDAS` → `TMU`,
`EGLINTON WEST` → `CEDARVALE`), truncation (`PIONEER VILLAGE STATIO`), typos (`KENENDY`), segments
(`FINCH TO ST CLAIR`), and places that aren't passenger stations (`GREENWOOD YARD`).

A wrong match is worse than no match: it would silently move delays to a station that didn't have them.

## Decision

Resolution runs a fixed sequence and stops at the first confident answer:

1. **Normalize**: upper case, drop punctuation and anything from `(` on, cut at the word `STATION` (or its
   truncations), and pull out line codes written in the name (`BD`, `YUS`) as hints.
2. **Classify** segments (`… TO …`, both ends must resolve), facilities and line-wide entries by keywords.
3. **Exact match** on canonical names, then a small alias table (renames, platform names, abbreviations).
4. **Prefix match** for truncated values: only if the prefix has at least 5 characters and points to a single
   station.
5. **Fuzzy match** with `difflib` for typos: only if the score is ≥ 0.85 *and* clearly ahead of the best match
   for any other station.

Anything else is `UNRESOLVED` and stays visible in the import report instead of being guessed.

## Consequences

- On the 2025–2026 data: 94.5% of rows resolve to a station, 99.3% to a known location kind, and all 70
  stations are covered. Every non-exact match was reviewed by hand.
- Values for the closed Line 3 (`SCARBOROUGH CTR`) and places outside the subway are left unresolved on
  purpose.
- No external dependency: `difflib` is in the standard library and fast enough for ~1,300 distinct values.
- New aliases are one line in `stations.py` plus a test case.

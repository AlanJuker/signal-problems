# signal-problems

> *"We're experiencing delays due to signal problems."*: every Toronto commuter, at least once a week.

**signal-problems** turns the TTC's open subway delay logs into something you can actually use: a clean
station-level dataset, an API, a live line map, and a straight answer to *"how likely is my commute to
get hit?"*

🚧 Work in progress. See the [roadmap](#roadmap).

## Why this is harder than it looks

The [TTC Subway Delay Data](https://open.toronto.ca/dataset/ttc-subway-delay-data/) has ~45,000 incidents
since January 2025 (and back to 2014), but the `Station` column is free text typed by operators: **1,251 distinct
spellings for 70 stations**.

| Raw value in the dataset | What it actually is |
|---|---|
| `BLOOR STATION`, `YONGE BD STATION` | Bloor–Yonge, Line 1 and Line 2 platforms |
| `DUNDAS STATION`, `TMU STATION` | the same station, before and after its renaming |
| `PIONEER VILLAGE STATIO` | truncated at 22 characters |
| `SCABOROUGH TOWN CENTRE` | typo (and a closed line) |
| `FINCH TO ST CLAIR` | a segment, not a station |
| `GREENWOOD YARD` | a yard, not a passenger station |

Resolving that reliably, and being honest about what can't be resolved, is the core of the project.

## Roadmap

- [ ] Domain model and station resolver
- [ ] Ingestion pipeline (Toronto Open Data → PostgreSQL)
- [ ] REST API
- [ ] Web app: line map, station detail, commute check
- [ ] Commute delay-risk model, evaluated against a historical baseline
- [ ] Deployment

## Data

Contains information licensed under the
[Open Government Licence – Toronto](https://open.toronto.ca/open-data-license/).

## License

[MIT](LICENSE)

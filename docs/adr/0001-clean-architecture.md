# 1. Clean architecture with ports and adapters

Date: 2026-10-14
Status: Accepted

## Context

The interesting logic in this project lives in two places: resolving messy station names, and turning raw
incidents into statistics a commuter can trust. Both should be testable without a database, an HTTP server or
the Toronto Open Data portal being up.

## Decision

The backend is split into four layers. Dependencies only point inwards:

```
api ──► application ──► domain
 │           ▲
 └──► infrastructure (implements domain ports)
```

- **domain**: entities, value objects and pure services (station registry and resolver, delay causes, commute
  risk). No framework imports.
- **application**: use cases that orchestrate the domain through *ports* (`DelayRepository`, `DelaySource`),
  defined as `typing.Protocol`.
- **infrastructure**: adapters for those ports (SQLAlchemy + PostgreSQL, Toronto Open Data CKAN client).
- **api**: FastAPI routers and HTTP schemas. It is the composition root that wires adapters into use cases.

## Consequences

- Domain and application tests run in milliseconds with in-memory fakes.
- Swapping PostgreSQL or the data source only touches `infrastructure`.
- There is some mapping code between ORM rows, domain objects and HTTP schemas. It keeps persistence and
  transport details from leaking into the domain.

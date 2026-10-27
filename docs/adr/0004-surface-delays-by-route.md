# 4. Streetcar and bus delays by route

Date: 2026-10-27
Status: Accepted

## Context

The streetcar and bus logs (#28) have the subway's columns, but `Station` holds a free-text location, mostly an
intersection cut at 22 characters ("RONCESVALLES AND HOWAR"): 3,130 distinct values for streetcars and 16,396
for buses since 2025. Unlike the 70 subway stations ([ADR 0002](0002-station-resolution.md)), there is no fixed
list to resolve them against. Matching them to stops would need the GTFS stop list and geocoding of truncated
intersection names, and every guess would move delays to a place that may not have had them.

`Line` names the route ("504 KING"), and 98% of rows start with the route number.

## Decision

- **The route is the unit.** It's taken from the logged line's leading number, so the branch "504A KING" counts
  as 504. Lines without one ("LINE 1 SHUTTLE", "RAD", empty) are counted and listed by ingest, never guessed.
- **Locations are kept as logged**, so a route profile can show where its delays are written down most often,
  without claiming to know the exact stop.
- **A separate `surface_delays` table**, so the subway's tables, endpoints and commute check can't change.
- **Each mode's own code list** for cause descriptions. The prefixes match the subway's, so cause categories work
  the same way.

## Consequences

- Since 2025: 23,265 streetcar and 100,289 bus delays stored; 420 and 1,670 rows reported without a route.
- A commute check for streetcar and bus trips isn't possible yet: it would need stops along a route.
- 2014–2024 uses another schema (`Route`, `Location`, `Incident` words instead of codes) and is left for a
  second phase.
- If routes prove too coarse, resolving locations to GTFS stops can come later, with its own report of what
  matched, like the subway resolver.

# 5. Incident words in the 2014–2024 streetcar and bus logs

Date: 2026-11-10
Status: Accepted

## Context

[ADR 0004](0004-surface-delays-by-route.md) stores streetcar and bus delays since 2025, which carry the same
kind of cause codes as the subway ("MTDV", "EFD"). The yearly 2014–2024 workbooks (#28) don't. Their
`Incident` column holds one of about 35 words instead ("Mechanical", "Held By", "Diversion"), and there's no
year logged both ways, so no row says which code a word became.

The workbooks also rename columns over the years: `Report Date` or `Date`, `Route` or `Line`, `Delay` or
`Min Delay`, `Direction` or `Bound`. One 2019 sheet adds an `Incident ID`.

## Decision

- **A word takes the category of the code with the same meaning in that mode's current list.** "Diversion"
  is MTDV and MFDV, ON DIVERSION, so it's a passenger-and-other delay. Words with no such code, or with codes
  in two categories, stay uncategorized instead of guessed.
- **Words are stored as logged**, tidied and upper-cased like the published code lists, so a route profile
  can name them. `cause_code` grows to 40 characters to fit them.
- **Each field accepts every column name it went by.** Bus sheets must say `Route` and `Direction`: see the
  copied sheets below.

| Category | Words (the matching code) | Streetcar rows | Bus rows |
|---|---|---|---|
| Equipment | Mechanical (every E code is a vehicle system); Late Leaving Garage - Mechanical | 46,426 | 248,711 |
| Operations | Operations, Operations - Operator; Late, Late Entering Service, Late Leaving Garage (TTLF, TFLF late entering service); Collision - TTC (TTPD, TFPD) | 30,147 | 131,877 |
| Passengers and other | General Delay (MTGD); Investigation for streetcars (MTPOL); Diversion (MTDV, MFDV); Cleaning (MTCN, MFCN, MTSAN); Vision (MFVIS); Road Blocked - Non-TTC Collision (MTPI, MFPI) | 35,700 | 144,510 |
| Security | Security; Investigation for buses (SFPOL, held due to police investigation) | 6,398 | 67,060 |
| Infrastructure | Overhead (PTOV); Rail/Switches (PTW, PTSW) | 642 | 0 |
| Uncategorized | Utilized Off Route; Emergency Services; Held By; Management; Overhead - Pantograph; blank | 27,127 (18.5%) | 109,190 (15.6%) |

Two of these needed a closer look:

- **Investigation** is a passenger code for streetcars (MTPOL, police investigation) and a security code for
  buses (SFPOL). Each mode keeps its own list's category.
- **Collision - TTC** has codes under both operations (TTPD, TFPD) and plant (PTPD, PFPD). Since 2025, 7,981
  of the 7,989 TTC-collision delays carry the operations codes, so it's operations.

The uncategorized words are real causes, just not ones the code lists settle. "Held By" could be police
(SFPOL, security) or a parade (MFPR, passengers). "Utilized Off Route" is a vehicle taken for other service;
the closest code, MFSH (used as shuttle bus), covers only part of it. Ingest reports them with their row
counts.

## The copied bus sheets

The 2021 bus workbook's July and August sheets are the only bus sheets headed `Line` and `Bound`. They repeat
the streetcar workbook's July and August sheets row for row (1,074 and 1,229 rows, identical). Fingerprints
don't include the mode, so whichever mode was ingested second lost those rows as "already stored". With
streetcars second, real streetcar delays would have been filed as bus delays.

Bus columns accept only `Route` and `Direction`, so those two sheets are skipped. The cost is real: **the
portal has no bus delays for July and August 2021.**

## Consequences

- Stored for 2014–2024: 146,440 streetcar and 701,348 bus delays. Ingest skipped 535 and 2,230 rows without a
  route number, and 6 and 33 malformed rows.
- 2014–2024 rows log only the route number, so a route's name comes from a spelling that has one ("504 KING"),
  however common the bare number is.
- Ranking 800,000 bus rows took about a second in SQLite. An index covering the ranking (mode, route, name,
  minutes, time) brings it to 73 ms.
- Before 2025 the category bars carry an uncategorized share of 15–19%, so comparisons across 2025 should
  allow for it.
- Route numbers are taken to mean the same route in every year.

import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import type { Schemas } from "../api/client";

const station = (id: string, name: string, lines: Schemas["Line"][]): Schemas["StationOut"] => ({
  id,
  name,
  lines,
});

// A tiny network with the shape the layout relies on: Line 1's U through St George, Union and
// Bloor-Yonge, Line 2 crossing it at Spadina, St George and Bloor-Yonge, Line 4 from Sheppard-Yonge.
export const LINES: Schemas["LineOut"][] = [
  {
    id: "1",
    name: "Line 1 Yonge–University",
    stations: [
      station("dupont", "Dupont", ["1"]),
      station("spadina", "Spadina", ["1", "2"]),
      station("st-george", "St George", ["1", "2"]),
      station("museum", "Museum", ["1"]),
      station("union", "Union", ["1"]),
      station("king", "King", ["1"]),
      station("bloor-yonge", "Bloor-Yonge", ["1", "2"]),
      station("sheppard-yonge", "Sheppard-Yonge", ["1", "4"]),
    ],
  },
  {
    id: "2",
    name: "Line 2 Bloor–Danforth",
    stations: [
      station("kipling", "Kipling", ["2"]),
      station("spadina", "Spadina", ["1", "2"]),
      station("st-george", "St George", ["1", "2"]),
      station("bay", "Bay", ["2"]),
      station("bloor-yonge", "Bloor-Yonge", ["1", "2"]),
      station("kennedy", "Kennedy", ["2"]),
    ],
  },
  {
    id: "4",
    name: "Line 4 Sheppard",
    stations: [
      station("sheppard-yonge", "Sheppard-Yonge", ["1", "4"]),
      station("don-mills", "Don Mills", ["4"]),
    ],
  },
];

const heat = (line: string) =>
  LINES.find((l) => l.id === line)!.stations.map((s) => ({
    station: s,
    incidents: 10,
    significant: s.id === "union" ? 40 : 2,
    minutes_lost: 30,
  }));

export const UNION: Schemas["StationProfileOut"] = {
  station: station("union", "Union", ["1"]),
  incidents: 900,
  significant: 140,
  minutes_lost: 2_150,
  categories: { security: 60, infrastructure: 20 },
  top_causes: [
    {
      code: "SUDP",
      description: "Disorderly Patron",
      category: "security",
      is_signal_problem: false,
      count: 33,
    },
    {
      code: "PUSI",
      description: "Signals or Related Components Failure",
      category: "infrastructure",
      is_signal_problem: true,
      count: 9,
    },
    {
      code: "TUNCA",
      description: null,
      category: "operations",
      is_signal_problem: false,
      count: 4,
    },
  ],
  by_weekday_hour: Array.from({ length: 7 }, (_, day) =>
    Array.from({ length: 24 }, (_, hour) => (day === 0 && hour === 8 ? 12 : 0)),
  ),
};

export const COMMUTE: Schemas["CommuteOut"] = {
  stations: [LINES[0].stations[6], LINES[0].stations[5], LINES[0].stations[4]],
  window_start: "08:00:00",
  window_end: "08:34:00",
  days_observed: 87,
  days_hit: 24,
  risk: 24 / 87,
  worst_stations: [{ station: LINES[0].stations[5], delays: 7 }],
  top_causes: UNION.top_causes,
};

export const server = setupServer(
  http.get("*/api/summary", () =>
    HttpResponse.json({
      first_day: "2025-01-01",
      last_day: "2026-08-31",
      incidents: 45_409,
      significant: 8_161,
      signal_problems: 309,
    }),
  ),
  http.get("*/api/lines", () => HttpResponse.json(LINES)),
  http.get("*/api/lines/:line/heat", ({ params }) => HttpResponse.json(heat(String(params.line)))),
  http.get("*/api/stations/:id", ({ params }) =>
    params.id === "union"
      ? HttpResponse.json(UNION)
      : HttpResponse.json({ detail: "Unknown station" }, { status: 404 }),
  ),
  http.post("*/api/commute/risk", () => HttpResponse.json(COMMUTE)),
);

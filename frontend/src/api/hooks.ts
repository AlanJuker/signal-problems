import { useMutation, useQueries, useQuery } from "@tanstack/react-query";

import { api, unwrap, type LineId, type Schemas } from "./client";

export const LINE_IDS: LineId[] = ["1", "2", "4"];

export function useSummary() {
  return useQuery({
    queryKey: ["summary"],
    queryFn: () => unwrap(api.GET("/summary")),
  });
}

export function useLines() {
  return useQuery({
    queryKey: ["lines"],
    queryFn: () => unwrap(api.GET("/lines")),
    staleTime: Infinity, // the network doesn't change while the page is open
  });
}

/** 5+ minute delays per station, merged across lines: interchanges take their busiest line. */
export function useStationHeat(since: string | undefined) {
  return useQueries({
    queries: LINE_IDS.map((line) => ({
      queryKey: ["heat", line, since],
      queryFn: () =>
        unwrap(api.GET("/lines/{line}/heat", { params: { path: { line }, query: { since } } })),
    })),
    combine: (results) => {
      const heat = new Map<string, number>();
      for (const result of results) {
        for (const item of result.data ?? []) {
          heat.set(item.station.id, Math.max(heat.get(item.station.id) ?? 0, item.significant));
        }
      }
      return { heat, isPending: results.some((r) => r.isPending) };
    },
  });
}

export function useStation(stationId: string | null, since: string | undefined) {
  return useQuery({
    queryKey: ["station", stationId, since],
    queryFn: () =>
      unwrap(
        api.GET("/stations/{station_id}", {
          params: { path: { station_id: stationId! }, query: { since } },
        }),
      ),
    enabled: stationId !== null,
  });
}

export function useCommuteRisk() {
  return useMutation({
    mutationFn: (body: Schemas["CommuteRequest"]) => unwrap(api.POST("/commute/risk", { body })),
  });
}

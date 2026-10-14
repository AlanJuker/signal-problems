import { useCallback, useState } from "react";

/** The selected station lives in `?station=…`, so a station's page can be shared. */
export function useStationParam(): [string | null, (stationId: string) => void] {
  const [station, setStation] = useState(() =>
    new URLSearchParams(window.location.search).get("station"),
  );
  const select = useCallback((stationId: string) => {
    const url = new URL(window.location.href);
    url.searchParams.set("station", stationId);
    window.history.replaceState(null, "", url);
    setStation(stationId);
  }, []);
  return [station, select];
}

import { useState } from "react";

import { PERIODS, parsePeriod, sinceFor, type Period } from "./period";
import { useSearchParam } from "./useSearchParam";

import { useLines, useStationHeat, useSummary } from "./api/hooks";
import { CommuteCheck } from "./features/commute/CommuteCheck";
import { SubwayMap } from "./features/map/SubwayMap";
import { StationPanel } from "./features/station/StationPanel";
import { Hero } from "./features/summary/Hero";

export function App() {
  const lines = useLines();
  const summary = useSummary();
  const [periodParam, setPeriod] = useSearchParam("period");
  const period = parsePeriod(periodParam);
  const since = sinceFor(period, summary.data?.last_day);
  const { heat } = useStationHeat(since);
  const [selected, setSelected] = useSearchParam("station");
  const [trip, setTrip] = useState<Set<string>>();

  return (
    <>
      <Hero />
      <main>
        <fieldset className="period">
          <legend>Based on</legend>
          {(Object.keys(PERIODS) as Period[]).map((key) => (
            <label key={key}>
              <input
                type="radio"
                name="period"
                value={key}
                checked={period === key}
                onChange={() => setPeriod(key)}
              />
              {PERIODS[key].label}
            </label>
          ))}
        </fieldset>
        <section className="map-card" aria-label="Delays by station">
          {lines.isError && <p role="alert">Couldn't load the subway lines.</p>}
          {lines.data && (
            <>
              <SubwayMap
                lines={lines.data}
                heat={heat}
                selected={selected}
                highlighted={trip}
                onSelect={setSelected}
              />
              <p className="legend">
                Bigger, darker stations had more delays of 5+ minutes. Select one for details.
              </p>
            </>
          )}
        </section>
        <div className="columns">
          <StationPanel stationId={selected} since={since} />
          {lines.data && <CommuteCheck lines={lines.data} since={since} onResult={setTrip} />}
        </div>
      </main>
      <footer>
        Data:{" "}
        <a href="https://open.toronto.ca/dataset/ttc-subway-delay-data/">TTC Subway Delay Data</a>,
        Toronto Open Data, under the{" "}
        <a href="https://open.toronto.ca/open-data-license/">Open Government Licence – Toronto</a>.
        Not affiliated with the TTC.
      </footer>
    </>
  );
}

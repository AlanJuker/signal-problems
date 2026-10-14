import { useState } from "react";

import { useStationParam } from "./useStationParam";

import { useLines, useStationHeat } from "./api/hooks";
import { CommuteCheck } from "./features/commute/CommuteCheck";
import { SubwayMap } from "./features/map/SubwayMap";
import { StationPanel } from "./features/station/StationPanel";
import { Hero } from "./features/summary/Hero";

export function App() {
  const lines = useLines();
  const { heat } = useStationHeat();
  const [selected, setSelected] = useStationParam();
  const [trip, setTrip] = useState<Set<string>>();

  return (
    <>
      <Hero />
      <main>
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
          <StationPanel stationId={selected} />
          {lines.data && <CommuteCheck lines={lines.data} onResult={setTrip} />}
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

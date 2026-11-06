import { useStation } from "../../api/hooks";
import { Breakdown } from "../Breakdown";
import "./StationPanel.css";

interface Props {
  stationId: string | null;
  since: string | undefined;
}

export function StationPanel({ stationId, since }: Props) {
  const { data, isPending, isError } = useStation(stationId, since);

  if (stationId === null) {
    return (
      <aside className="panel panel-empty">
        <p>Pick a station on the map to see what holds it up, and when.</p>
      </aside>
    );
  }
  if (isPending) return <aside className="panel" aria-busy="true" />;
  if (isError) {
    return (
      <aside className="panel" role="alert">
        Couldn't load this station. Try again in a moment.
      </aside>
    );
  }

  return (
    <aside className="panel" aria-labelledby="station-name">
      <header>
        <h2 id="station-name">{data.station.name}</h2>
        <ul className="line-badges" aria-label="Lines">
          {data.station.lines.map((line) => (
            <li key={line} className={`badge badge-${line}`}>
              {line}
            </li>
          ))}
        </ul>
      </header>
      <Breakdown totals={data} profile={data} />
    </aside>
  );
}

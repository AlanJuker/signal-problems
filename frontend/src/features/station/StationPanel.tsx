import { useStation } from "../../api/hooks";
import { CATEGORY_LABELS, describeCause } from "../causes";
import { WeekHourGrid } from "./WeekHourGrid";
import "./StationPanel.css";

const number = new Intl.NumberFormat("en-CA");

export function StationPanel({ stationId }: { stationId: string | null }) {
  const { data, isPending, isError } = useStation(stationId);

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

  const categories = Object.entries(data.categories).sort(([, a], [, b]) => b - a);
  const top = categories[0]?.[1] ?? 1;

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

      <dl className="stats">
        <div>
          <dt>Delays of 5+ min</dt>
          <dd>{number.format(data.significant)}</dd>
        </div>
        <div>
          <dt>Minutes lost</dt>
          <dd>{number.format(data.minutes_lost)}</dd>
        </div>
        <div>
          <dt>Logged incidents</dt>
          <dd>{number.format(data.incidents)}</dd>
        </div>
      </dl>

      <h3>What causes them</h3>
      <ul className="bars">
        {categories.map(([category, count]) => (
          <li key={category}>
            <span>{CATEGORY_LABELS[category as keyof typeof CATEGORY_LABELS]}</span>
            <span className="bar" aria-hidden="true">
              <span style={{ width: `${(count / top) * 100}%` }} />
            </span>
            <span className="count">{count}</span>
          </li>
        ))}
      </ul>

      <h3>Most common reasons</h3>
      <ol className="causes">
        {data.top_causes.map((cause) => (
          <li key={cause.code}>
            <span>
              {describeCause(cause)}
              {cause.is_signal_problem && <span className="tag">signal failure</span>}
            </span>
            <span className="count">{cause.count}</span>
          </li>
        ))}
      </ol>

      <h3>When</h3>
      <WeekHourGrid grid={data.by_weekday_hour} />
    </aside>
  );
}

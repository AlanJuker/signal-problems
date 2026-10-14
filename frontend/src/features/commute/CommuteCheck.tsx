import { useState, type FormEvent } from "react";

import type { LineId, Schemas } from "../../api/client";
import { useCommuteRisk } from "../../api/hooks";
import { describeCause } from "../causes";
import "./CommuteCheck.css";

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

interface Props {
  lines: Schemas["LineOut"][];
  onResult: (stationIds: Set<string> | undefined) => void;
}

export function CommuteCheck({ lines, onResult }: Props) {
  const [line, setLine] = useState<LineId>("1");
  const stations = lines.find((l) => l.id === line)?.stations ?? [];
  const [origin, setOrigin] = useState("bloor-yonge");
  const [destination, setDestination] = useState("union");
  const [weekday, setWeekday] = useState(0);
  const [departure, setDeparture] = useState("08:15");
  const risk = useCommuteRisk();

  const changeLine = (next: LineId) => {
    const nextStations = lines.find((l) => l.id === next)?.stations ?? [];
    setLine(next);
    setOrigin(nextStations[0]?.id ?? "");
    setDestination(nextStations.at(-1)?.id ?? "");
    risk.reset();
    onResult(undefined);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    risk.mutate(
      { line, origin, destination, weekday, departure },
      { onSuccess: (result) => onResult(new Set(result.stations.map((s) => s.id))) },
    );
  };

  return (
    <section className="commute" aria-labelledby="commute-title">
      <h2 id="commute-title">Will my commute get hit?</h2>
      <form onSubmit={submit}>
        <label>
          Line
          <select value={line} onChange={(e) => changeLine(e.target.value as LineId)}>
            {lines.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          From
          <select value={origin} onChange={(e) => setOrigin(e.target.value)}>
            {stations.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          To
          <select value={destination} onChange={(e) => setDestination(e.target.value)}>
            {stations.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Day
          <select value={weekday} onChange={(e) => setWeekday(Number(e.target.value))}>
            {WEEKDAYS.map((day, i) => (
              <option key={day} value={i}>
                {day}
              </option>
            ))}
          </select>
        </label>
        <label>
          Leaving at
          <input
            type="time"
            required
            value={departure}
            onChange={(e) => setDeparture(e.target.value)}
          />
        </label>
        <button type="submit" disabled={risk.isPending}>
          {risk.isPending ? "Checking…" : "Check"}
        </button>
      </form>

      <div aria-live="polite">
        {risk.isError && <p role="alert">Couldn't check that trip. Try again in a moment.</p>}
        {risk.data && <CommuteResult result={risk.data} weekday={WEEKDAYS[weekday]} />}
      </div>
    </section>
  );
}

function CommuteResult({ result, weekday }: { result: Schemas["CommuteOut"]; weekday: string }) {
  const percent = Math.round(result.risk * 100);
  const from = result.stations[0].name;
  const to = result.stations.at(-1)!.name;
  return (
    <div className="result">
      <p className="risk">
        <strong>{percent}%</strong>
        <span>
          On {result.days_hit} of {result.days_observed} {weekday}s, a delay of 5+ minutes hit{" "}
          {from} → {to} between {result.window_start.slice(0, 5)} and{" "}
          {result.window_end.slice(0, 5)}.
        </span>
      </p>
      {result.worst_stations.length > 0 && (
        <p>
          Usually at{" "}
          {result.worst_stations.map((s) => `${s.station.name} (${s.delays})`).join(", ")}.
        </p>
      )}
      {result.top_causes.length > 0 && (
        <p>
          Most often: {result.top_causes.slice(0, 3).map(describeCause).join(" · ").toLowerCase()}.
        </p>
      )}
      <p className="fine-print">
        A historical frequency across {result.stations.length} stations, not a forecast.
      </p>
    </div>
  );
}

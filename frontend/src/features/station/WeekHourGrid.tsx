import type { CSSProperties } from "react";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HOURS = Array.from({ length: 24 }, (_, h) => h);

/** 5+ minute delays by weekday and hour, as a table so screen readers can walk it. */
export function WeekHourGrid({ grid }: { grid: number[][] }) {
  const max = Math.max(1, ...grid.flat());
  return (
    <table className="week-hour">
      <caption className="visually-hidden">Delays of 5+ minutes by weekday and hour</caption>
      <thead>
        <tr>
          <td />
          {HOURS.map((h) => (
            <th key={h} scope="col">
              <abbr title={`${h}:00`}>{h % 6 === 0 ? h : ""}</abbr>
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {grid.map((row, day) => (
          <tr key={DAYS[day]}>
            <th scope="row">{DAYS[day]}</th>
            {row.map((count, hour) => (
              <td
                key={hour}
                title={`${DAYS[day]} ${hour}:00 · ${count}`}
                style={{ "--heat": `${Math.round((count / max) * 100)}%` } as CSSProperties}
              >
                <span className="visually-hidden">{count}</span>
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

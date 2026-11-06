import type { Schemas } from "../api/client";
import { CATEGORY_LABELS, describeCause } from "./causes";
import { WeekHourGrid } from "./station/WeekHourGrid";

const number = new Intl.NumberFormat("en-CA");

interface Props {
  totals: { significant: number; minutes_lost: number; incidents: number };
  profile: Pick<Schemas["StationProfileOut"], "categories" | "top_causes" | "by_weekday_hour">;
  labels?: Record<Schemas["CauseCategory"], string>;
}

/** What a station's or a route's delays add up to, what causes them, and when they happen. */
export function Breakdown({ totals, profile, labels = CATEGORY_LABELS }: Props) {
  const categories = Object.entries(profile.categories).sort(([, a], [, b]) => b - a);
  const top = categories[0]?.[1] ?? 1;

  return (
    <>
      <dl className="stats">
        <div>
          <dt>Delays of 5+ min</dt>
          <dd>{number.format(totals.significant)}</dd>
        </div>
        <div>
          <dt>Minutes lost</dt>
          <dd>{number.format(totals.minutes_lost)}</dd>
        </div>
        <div>
          <dt>Logged incidents</dt>
          <dd>{number.format(totals.incidents)}</dd>
        </div>
      </dl>

      <h3>What causes them</h3>
      <ul className="bars">
        {categories.map(([category, count]) => (
          <li key={category}>
            <span>{labels[category as Schemas["CauseCategory"]]}</span>
            <span className="bar" aria-hidden="true">
              <span style={{ width: `${(count / top) * 100}%` }} />
            </span>
            <span className="count">{count}</span>
          </li>
        ))}
      </ul>

      <h3>Most common reasons</h3>
      <ol className="causes">
        {profile.top_causes.map((cause) => (
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
      <WeekHourGrid grid={profile.by_weekday_hour} />
    </>
  );
}

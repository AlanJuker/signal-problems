import { useSummary } from "../../api/hooks";

const number = new Intl.NumberFormat("en-CA");
const month = new Intl.DateTimeFormat("en-CA", { month: "long", year: "numeric", timeZone: "UTC" });

export function Hero() {
  const { data } = useSummary();
  const share = data && data.significant ? (data.signal_problems / data.significant) * 100 : null;

  return (
    <header className="hero">
      <p className="kicker">“We're experiencing delays due to signal problems.”</p>
      <h1>
        Is it really <em>signal problems?</em>
      </h1>
      {data && share !== null ? (
        <p className="answer">
          Only <strong>{share.toFixed(1)}%</strong> of the {number.format(data.significant)} subway
          delays of 5+ minutes between {month.format(new Date(data.first_day!))} and{" "}
          {month.format(new Date(data.last_day!))} were signal failures. Here's what actually holds
          the trains, station by station.
        </p>
      ) : (
        <p className="answer" aria-busy="true">
          Loading the TTC delay log…
        </p>
      )}
    </header>
  );
}

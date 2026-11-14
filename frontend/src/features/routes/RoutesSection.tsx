import { ApiError, type Schemas } from "../../api/client";
import { useRoute, useRoutes } from "../../api/hooks";
import { useSearchParam } from "../../useSearchParam";
import { Breakdown } from "../Breakdown";
import { CATEGORY_LABELS } from "../causes";
import "./RoutesSection.css";

type Mode = Schemas["Mode"];

const MODES: Record<Mode, string> = { streetcar: "Streetcars", bus: "Buses" };
const TOP = 10;
const number = new Intl.NumberFormat("en-CA");

// On the street, equipment codes are the vehicle's, and plant codes are track, switches and overhead
const LABELS = {
  ...CATEGORY_LABELS,
  equipment: "Vehicles & equipment",
  infrastructure: "Track, switches & overhead",
};

export function RoutesSection({ since }: { since: string | undefined }) {
  const [modeParam, setMode] = useSearchParam("mode");
  const [routeParam, setRoute] = useSearchParam("route");
  const mode: Mode = modeParam === "bus" ? "bus" : "streetcar";
  const routes = useRoutes(mode, since);
  const route = routeParam !== null ? Number(routeParam) : (routes.data?.[0]?.route ?? null);

  return (
    <section className="routes" aria-labelledby="routes-title">
      <h2 id="routes-title">Streetcars and buses, by route</h2>
      <p className="legend">
        The TTC's streetcar and bus logs start in January 2025, so longer periods begin there.
      </p>
      <fieldset className="pills">
        <legend className="visually-hidden">Mode</legend>
        {(Object.keys(MODES) as Mode[]).map((key) => (
          <label key={key}>
            <input
              type="radio"
              name="mode"
              value={key}
              checked={mode === key}
              onChange={() => {
                setMode(key);
                setRoute(null);
              }}
            />
            {MODES[key]}
          </label>
        ))}
      </fieldset>
      <div className="columns">
        <div className="panel">
          {routes.isError && <p role="alert">Couldn't load the routes.</p>}
          {routes.data && (
            <Ranking routes={routes.data} selected={route} onSelect={(r) => setRoute(String(r))} />
          )}
        </div>
        {route !== null && <RoutePanel mode={mode} route={route} since={since} />}
      </div>
    </section>
  );
}

interface RankingProps {
  routes: Schemas["RouteOut"][];
  selected: number | null;
  onSelect: (route: number) => void;
}

function Ranking({ routes, selected, onSelect }: RankingProps) {
  if (routes.length === 0) return <p>No delays logged in this period.</p>;
  const top = routes.slice(0, TOP);
  const max = Math.max(1, top[0].significant);
  const byNumber = [...routes].sort((a, b) => a.route - b.route);

  return (
    <>
      <h3>Most delays of 5+ minutes</h3>
      <ol className="ranking">
        {top.map((r) => (
          <li key={r.route}>
            <button
              type="button"
              aria-pressed={r.route === selected}
              aria-label={`${r.name}: ${number.format(r.significant)} delays of 5+ minutes`}
              onClick={() => onSelect(r.route)}
            >
              <span>{r.name}</span>
              <span className="bar" aria-hidden="true">
                <span style={{ width: `${(r.significant / max) * 100}%` }} />
              </span>
              <span className="count">{number.format(r.significant)}</span>
            </button>
          </li>
        ))}
      </ol>
      <label className="any-route">
        Any of the {routes.length} routes
        <select value={selected ?? ""} onChange={(e) => onSelect(Number(e.target.value))}>
          {byNumber.map((r) => (
            <option key={r.route} value={r.route}>
              {r.name}
            </option>
          ))}
        </select>
      </label>
    </>
  );
}

function RoutePanel({ mode, route, since }: { mode: Mode; route: number; since?: string }) {
  const { data, isPending, isError, error } = useRoute(mode, route, since);

  if (isPending) return <aside className="panel" aria-busy="true" />;
  if (isError) {
    return (
      <aside className="panel" role="alert">
        {error instanceof ApiError && error.status === 404
          ? `No delays logged on ${mode} route ${route} in this period.`
          : "Couldn't load this route. Try again in a moment."}
      </aside>
    );
  }

  return (
    <aside className="panel" aria-labelledby="route-name">
      <header>
        <h2 id="route-name">{data.route.name}</h2>
      </header>
      <Breakdown totals={data.route} profile={data} labels={LABELS} />
      {data.top_locations.length > 0 && (
        <>
          <h3>Where they're logged most</h3>
          <ol className="causes">
            {data.top_locations.map((l) => (
              <li key={l.location}>
                <span>{l.location}</span>
                <span className="count">{l.delays}</span>
              </li>
            ))}
          </ol>
        </>
      )}
    </aside>
  );
}

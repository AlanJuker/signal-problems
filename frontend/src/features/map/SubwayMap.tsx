import { useMemo, type CSSProperties, type KeyboardEvent } from "react";

import type { LineId, Schemas } from "../../api/client";
import { computeLayout } from "./layout";
import "./SubwayMap.css";

interface Props {
  lines: Schemas["LineOut"][];
  heat: Map<string, number>;
  selected: string | null;
  highlighted?: Set<string>;
  onSelect: (stationId: string) => void;
}

export function SubwayMap({ lines, heat, selected, highlighted, onSelect }: Props) {
  const layout = useMemo(
    () =>
      computeLayout(
        Object.fromEntries(lines.map((l) => [l.id, l.stations.map((s) => s.id)])) as Record<
          LineId,
          string[]
        >,
      ),
    [lines],
  );
  const stations = useMemo(
    () => new Map(lines.flatMap((l) => l.stations.map((s) => [s.id, s] as const))),
    [lines],
  );
  const max = Math.max(1, ...heat.values());

  return (
    <div className="map-scroll">
      <svg
        className="subway-map"
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        role="group"
        aria-label="Subway map. Each station shows its number of delays of 5 minutes or more."
      >
        {(["2", "1", "4"] as const).map((line) => (
          <polyline
            key={line}
            className={`route route-${line}`}
            points={layout.routes[line].map((p) => `${p.x},${p.y}`).join(" ")}
          />
        ))}
        {[...layout.nodes].map(([id, node]) => {
          const station = stations.get(id)!;
          const delays = heat.get(id) ?? 0;
          const share = delays / max;
          const dimmed = highlighted && !highlighted.has(id);
          const select = () => onSelect(id);
          const onKeyDown = (event: KeyboardEvent) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              select();
            }
          };
          return (
            <g
              key={id}
              className="station"
              data-dimmed={dimmed || undefined}
              data-selected={selected === id || undefined}
              role="button"
              tabIndex={0}
              aria-pressed={selected === id}
              aria-label={`${station.name}: ${delays} delays of 5+ minutes`}
              onClick={select}
              onKeyDown={onKeyDown}
              transform={`translate(${node.x} ${node.y})`}
            >
              <title>{`${station.name} · ${delays} delays of 5+ min`}</title>
              <circle className="hit-area" r={14} />
              <circle
                className={station.lines.length > 1 ? "marker interchange" : "marker"}
                r={5 + 7 * Math.sqrt(share)}
                style={{ "--heat": `${Math.round(share * 100)}%` } as CSSProperties}
              />
              <text
                className="label"
                x={node.label.dx}
                y={node.label.dy}
                textAnchor={node.label.anchor}
                transform={node.label.rotate ? `rotate(${node.label.rotate})` : undefined}
              >
                {station.name}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

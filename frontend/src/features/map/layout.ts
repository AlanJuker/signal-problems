/**
 * Schematic layout in the spirit of the TTC's own map: Line 2 runs west–east, Line 1 is a U with
 * Union at the bottom, Line 4 heads east from Sheppard-Yonge. Positions come from each line's
 * station order, anchored on a few interchanges, so the map follows the API instead of a
 * hand-drawn list of coordinates.
 */
import type { LineId } from "../../api/client";

export const DX = 34; // between stations along Line 2 and Line 4
export const DY = 26; // between stations along Line 1
const LEFT = 70;
const TOP = 24;

export type Anchor = "start" | "end" | "middle";

export interface Label {
  dx: number;
  dy: number;
  anchor: Anchor;
  rotate: number;
}

export interface Node {
  x: number;
  y: number;
  label: Label;
}

export interface MapLayout {
  width: number;
  height: number;
  nodes: Map<string, Node>;
  routes: Record<LineId, Array<{ x: number; y: number }>>;
}

const right: Label = { dx: 9, dy: 4, anchor: "start", rotate: 0 };
const left: Label = { dx: -9, dy: 4, anchor: "end", rotate: 0 };
const downLeft: Label = { dx: -6, dy: 12, anchor: "end", rotate: -45 };
const upRight: Label = { dx: 6, dy: -10, anchor: "start", rotate: -45 };
const downRight: Label = { dx: 6, dy: 12, anchor: "start", rotate: 45 };
const below: Label = { dx: 0, dy: 20, anchor: "middle", rotate: 0 };

export function computeLayout(lines: Record<LineId, string[]>): MapLayout {
  const nodes = new Map<string, Node>();
  const line1 = lines["1"];
  const line2 = lines["2"];
  const line4 = lines["4"];
  const northOfSpadina = line1.indexOf("spadina");
  const y2 = TOP + northOfSpadina * DY;
  const x2 = (id: string) => LEFT + line2.indexOf(id) * DX;

  // Line 2: labels hang below-left in the west and rise to the right in the east,
  // leaving room for the arms of Line 1.
  const xBloorYonge = x2("bloor-yonge");
  line2.forEach((id, i) => {
    const x = LEFT + i * DX;
    nodes.set(id, { x, y: y2, label: x > xBloorYonge ? upRight : downLeft });
  });

  // Line 1, travelling Vaughan → Union → Finch.
  const xSpadina = x2("spadina");
  const xStGeorge = x2("st-george");
  const iStGeorge = line1.indexOf("st-george");
  const iUnion = line1.indexOf("union");
  const iBloorYonge = line1.indexOf("bloor-yonge");
  line1.forEach((id, i) => {
    if (i < northOfSpadina) {
      nodes.set(id, { x: xSpadina, y: y2 - (northOfSpadina - i) * DY, label: left });
    } else if (i > iStGeorge && i < iUnion) {
      nodes.set(id, { x: xStGeorge, y: y2 + (i - iStGeorge) * DY, label: left });
    } else if (i === iUnion) {
      const x = (xStGeorge + xBloorYonge) / 2;
      nodes.set(id, { x, y: y2 + (iUnion - iStGeorge) * DY, label: below });
    } else if (i > iUnion && i < iBloorYonge) {
      nodes.set(id, { x: xBloorYonge, y: y2 + (iBloorYonge - i) * DY, label: right });
    } else if (i > iBloorYonge) {
      nodes.set(id, { x: xBloorYonge, y: y2 - (i - iBloorYonge) * DY, label: left });
    }
  });

  // Interchanges sit on Line 2; move their labels clear of both lines.
  setLabel(nodes, "spadina", { dx: -9, dy: -8, anchor: "end", rotate: 0 });
  setLabel(nodes, "st-george", { dx: 8, dy: -9, anchor: "start", rotate: 0 });
  setLabel(nodes, "bloor-yonge", { dx: 9, dy: 15, anchor: "start", rotate: 0 });
  setLabel(nodes, "bay", { dx: 0, dy: 20, anchor: "middle", rotate: 0 });

  // Line 4, east from Sheppard-Yonge.
  const origin = nodes.get(line4[0])!;
  line4.slice(1).forEach((id, i) => {
    nodes.set(id, { x: origin.x + (i + 1) * DX * 1.4, y: origin.y, label: downRight });
  });

  const routes = {
    "1": line1.map((id) => nodes.get(id)!),
    "2": line2.map((id) => nodes.get(id)!),
    "4": line4.map((id) => nodes.get(id)!),
  };
  const all = [...nodes.values()];
  return {
    width: Math.max(...all.map((n) => n.x)) + LEFT,
    height: Math.max(...all.map((n) => n.y)) + 40,
    nodes,
    routes,
  };
}

function setLabel(nodes: Map<string, Node>, id: string, label: Label) {
  const node = nodes.get(id);
  if (node) nodes.set(id, { ...node, label });
}

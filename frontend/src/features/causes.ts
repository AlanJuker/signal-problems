import type { Schemas } from "../api/client";

export const CATEGORY_LABELS: Record<Schemas["CauseCategory"], string> = {
  passengers_and_other: "Passengers & other",
  security: "Security",
  infrastructure: "Signals, track & stations",
  operations: "Crew & operations",
  equipment: "Trains & equipment",
  unknown: "Undocumented code",
};

export function describeCause(cause: Schemas["CauseOut"]): string {
  return cause.description ?? `Code ${cause.code} (not in the TTC's published list)`;
}

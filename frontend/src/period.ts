export const PERIODS = {
  "12m": { label: "Past 12 months", days: 365 },
  "3y": { label: "Past 3 years", days: 3 * 365 },
  all: { label: "Since 2014", days: null },
} as const;

export type Period = keyof typeof PERIODS;

export function parsePeriod(value: string | null): Period {
  return value !== null && value in PERIODS ? (value as Period) : "12m";
}

/** First day of the period, counted back from the last day in the data (ISO date). */
export function sinceFor(period: Period, lastDay: string | null | undefined): string | undefined {
  const days = PERIODS[period].days;
  if (days === null || !lastDay) return undefined;
  const since = new Date(`${lastDay}T00:00:00Z`);
  since.setUTCDate(since.getUTCDate() - days + 1);
  return since.toISOString().slice(0, 10);
}

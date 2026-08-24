import { HUMAN_FLOOR } from "./types";

/**
 * Colour ramp for word error rate.
 *
 * Deliberately not a continuous gradient from 0. Anything at or below the
 * human-disagreement floor is drawn as one colour, because a model at 8% and a
 * model at 12% are not distinguishable and a smooth ramp would invent a
 * difference the data cannot support.
 */
const STOPS: Array<{ max: number; fill: string; label: string }> = [
  { max: HUMAN_FLOOR.high, fill: "#1a7f5a", label: "at the human floor" },
  { max: 0.25, fill: "#5aa15f", label: "15 to 25%" },
  { max: 0.4, fill: "#c8a63a", label: "25 to 40%" },
  { max: 0.6, fill: "#d2703a", label: "40 to 60%" },
  { max: Infinity, fill: "#a8322f", label: "over 60%" },
];

export const NO_DATA_FILL = "var(--no-data)";

export function fillFor(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return NO_DATA_FILL;
  return (STOPS.find((s) => value <= s.max) ?? STOPS[STOPS.length - 1]).fill;
}

export const LEGEND = STOPS;

export const pct = (v: number | null | undefined) =>
  v === null || v === undefined || Number.isNaN(v) ? "no data" : `${(v * 100).toFixed(1)}%`;

import { HUMAN_FLOOR } from "./types";

/**
 * Colour ramp for error rate.
 *
 * Two deliberate choices.
 *
 * It is not a continuous gradient from zero. Everything at or below the
 * human-disagreement floor is one colour, because a model at 8% and a model at
 * 12% are not distinguishable and a smooth ramp would invent a difference the
 * data cannot support.
 *
 * The ramp varies in lightness as well as hue, so it survives red/green colour
 * blindness. The bands run teal to sand to rust rather than green to red, and
 * every band is also given a hatch density and a label so colour is never the
 * only carrier of the value.
 */
export type Band = {
  max: number;
  fill: string;
  label: string;
  short: string;
  /** Redundant encoding: how dense the diagonal hatch overlay is, 0 = none. */
  hatch: 0 | 1 | 2 | 3;
};

const STOPS: Band[] = [
  { max: HUMAN_FLOOR.high, fill: "#0f6f57", label: "at the human floor", short: "≤15%", hatch: 0 },
  { max: 0.25, fill: "#4f9a6f", label: "15 to 25%", short: "15–25%", hatch: 0 },
  { max: 0.4, fill: "#c9a227", label: "25 to 40%", short: "25–40%", hatch: 1 },
  { max: 0.6, fill: "#cf7238", label: "40 to 60%", short: "40–60%", hatch: 2 },
  { max: Infinity, fill: "#a12f2f", label: "over 60%", short: ">60%", hatch: 3 },
];

export const NO_DATA_FILL = "var(--no-data)";
export const LEGEND = STOPS;

export function bandFor(value: number | null | undefined): Band | null {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  return STOPS.find((s) => value <= s.max) ?? STOPS[STOPS.length - 1];
}

export function fillFor(value: number | null | undefined): string {
  return bandFor(value)?.fill ?? NO_DATA_FILL;
}

export const pct = (v: number | null | undefined) =>
  v === null || v === undefined || Number.isNaN(v) ? "no data" : `${(v * 100).toFixed(1)}%`;

/** Width of the inline magnitude bar in the table, capped so >100% still fits. */
export const barWidth = (v: number | null | undefined) =>
  v === null || v === undefined ? 0 : Math.min(100, Math.max(2, v * 100));

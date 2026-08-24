import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import type { Results, ProviderRun } from "./types";

// Vercel uploads only this directory, so the JSON the site reads is synced
// into public/data by scripts/sync-data.mjs and committed. See that file.
const DATA = join(process.cwd(), "public", "data");

/** Results are precomputed by the Python harness. Nothing is scored at request
 *  time, so the site is a static read of a JSON file. */
export function loadResults(): Results {
  const path = join(DATA, "results.json");
  if (!existsSync(path)) return { runs: [] };
  return JSON.parse(readFileSync(path, "utf8")) as Results;
}

export function loadCalibration(): Record<string, unknown> | null {
  const path = join(DATA, "calibration.json");
  if (!existsSync(path)) return null;
  return JSON.parse(readFileSync(path, "utf8"));
}

export function loadTopology() {
  return JSON.parse(
    readFileSync(join(process.cwd(), "public", "india-districts.topo.json"), "utf8"),
  );
}

/** Districts with Vaani audio but no polygon in the 2021 boundary release.
 *  Named on the page rather than silently missing. */
export function loadUnmapped(): Array<{ state: string; district: string; reason: string }> {
  const path = join(DATA, "district_crosswalk.json");
  if (!existsSync(path)) return [];
  const cw = JSON.parse(readFileSync(path, "utf8"));
  return (cw.unmatched ?? []).map((r: { state: string; district: string; reason?: string }) => ({
    state: r.state,
    district: r.district,
    reason: r.reason ?? "no boundary match",
  }));
}

export function districtValues(run: ProviderRun, language: string | null) {
  const out: Record<string, number | null> = {};
  const rows = language
    ? run.by_language_district.filter((a) => a.key[0] === language)
    : run.by_district;
  for (const a of rows) {
    const district = language ? a.key[1] : a.key[0];
    out[district] = a.primary;
  }
  return out;
}

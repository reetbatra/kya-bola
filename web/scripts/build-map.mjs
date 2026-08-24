/**
 * Build the district TopoJSON the site ships.
 *
 * Source is geoBoundaries gbOpen IND ADM2 (ODbL), which is derived from India's
 * own LGD directory. The per-country file is used deliberately: geoBoundaries'
 * CGAZ composite follows US State Department lines for disputed areas, which do
 * not match India's official boundary.
 *
 * Every district ships, not just the ones with data. A district we did not
 * measure renders grey; dropping it would leave a hole in the map that reads as
 * "nothing to see here".
 */
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const DATA = new URL("../../data/", import.meta.url).pathname;
const OUT = new URL("../public/india-districts.topo.json", import.meta.url).pathname;

const geo = JSON.parse(readFileSync(join(DATA, "ind_adm2_simplified.geojson"), "utf8"));
const crosswalk = JSON.parse(readFileSync(join(DATA, "district_crosswalk.json"), "utf8"));

// shapeID -> the Vaani district it carries data for.
const byShape = new Map();
for (const row of crosswalk.matched) {
  for (const id of row.shape_ids) {
    byShape.set(id, { district: row.district, state: row.state });
  }
}

let tagged = 0;
for (const f of geo.features) {
  const hit = byShape.get(f.properties.shapeID);
  f.properties = {
    id: f.properties.shapeID,
    name: f.properties.shapeName,
    ...(hit ? { vaani: hit.district, state: hit.state } : {}),
  };
  if (hit) tagged += 1;
}

const tmp = mkdtempSync(join(tmpdir(), "kyabola-"));
const src = join(tmp, "districts.geojson");
writeFileSync(src, JSON.stringify(geo));

// 8% simplification keeps district shapes recognisable at national zoom while
// cutting the payload by more than an order of magnitude.
const bin = new URL("../node_modules/.bin/mapshaper", import.meta.url).pathname;
execFileSync(bin, [
  src,
  "-simplify", "8%", "keep-shapes",
  "-o", "format=topojson", OUT,
], { stdio: "inherit" });

const kb = (n) => `${(n / 1024).toFixed(0)} KB`;
console.log(`districts: ${geo.features.length}, with Vaani data: ${tagged}`);
console.log(`source ${kb(statSync(src).size)} -> topojson ${kb(statSync(OUT).size)}`);

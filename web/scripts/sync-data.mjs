/**
 * Copy the JSON the site reads into web/public/data/.
 *
 * Vercel uploads only the project root (web/), so ../data does not exist in the
 * build image. These files are small and committed; the audio and manifests
 * they were derived from are not.
 */
import { copyFileSync, mkdirSync, existsSync, statSync } from "node:fs";
import { join } from "node:path";

const SRC = new URL("../../data/", import.meta.url).pathname;
const DST = new URL("../public/data/", import.meta.url).pathname;
mkdirSync(DST, { recursive: true });

for (const name of ["results.json", "calibration.json", "district_crosswalk.json"]) {
  const from = join(SRC, name);
  if (!existsSync(from)) {
    console.warn(`  skip ${name} (not generated yet)`);
    continue;
  }
  copyFileSync(from, join(DST, name));
  console.log(`  ${name} ${(statSync(from).size / 1024).toFixed(0)} KB`);
}

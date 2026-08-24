/** Mirror harness/languages.py into a JSON the site can read at build time. */
import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";

const root = new URL("../../", import.meta.url).pathname;
const out = execFileSync(
  "uv",
  ["run", "python", "-c",
   "import json;from harness.languages import LANGUAGES;" +
   "print(json.dumps({'supported':{k:v.supported for k,v in LANGUAGES.items()}," +
   "'clips':{k:v.clips for k,v in LANGUAGES.items()}}))"],
  { cwd: root, encoding: "utf8" },
);
writeFileSync(new URL("../public/languages.json", import.meta.url).pathname, out.trim());
console.log("wrote public/languages.json");

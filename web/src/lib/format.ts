/**
 * Display names.
 *
 * Provider ids are pipeline identifiers (`sarvam:saaras:v3`), which are the
 * right thing to key results on and the wrong thing to put in a button. Casing
 * for known vendor and model tokens is table-driven; anything unrecognised
 * falls back to plain capitalisation rather than being dropped, so a provider
 * added to the harness tomorrow still renders.
 */
const CASING: Record<string, string> = {
  indicconformer: "IndicConformer",
  sarvam: "Sarvam",
  saaras: "Saaras",
  elevenlabs: "ElevenLabs",
  scribe: "Scribe",
  ctc: "CTC",
  rnnt: "RNN-T",
  ai4bharat: "AI4Bharat",
  google: "Google",
  openai: "OpenAI",
  whisper: "Whisper",
  azure: "Azure",
};

function pretty(token: string): string {
  const known = CASING[token.toLowerCase()];
  if (known) return known;
  if (/^v\d/i.test(token)) return token.toLowerCase();
  return token.charAt(0).toUpperCase() + token.slice(1);
}

export function providerVendor(id: string): string {
  return pretty(id.split(":")[0] ?? id);
}

export function providerModel(id: string): string {
  return id.split(":").slice(1).map(pretty).join(" ");
}

export function providerLabel(id: string): string {
  return [providerVendor(id), providerModel(id)].filter(Boolean).join(" ");
}

/**
 * Vaani writes place names without spaces: `MadhyaPradesh`, `KomaramBheem`,
 * `WestGaroHills`. Those strings are the join keys between the corpus, the
 * crosswalk and the boundary file, so they are never rewritten in data, only on
 * the way to the screen.
 */
export function placeLabel(raw: string | undefined): string {
  if (!raw) return "";
  return raw
    .replace(/([a-z\d])([A-Z])/g, "$1 $2")
    .replace(/([A-Z]+)([A-Z][a-z])/g, "$1 $2")
    .replace(/\bAnd\b/g, "and")
    .trim();
}

export const nf = new Intl.NumberFormat("en-IN");

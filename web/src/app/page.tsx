import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { Explorer } from "@/components/Explorer";
import { CoverageTable } from "@/components/CoverageTable";
import { loadResults, loadTopology, loadUnmapped, loadCalibration } from "@/lib/data";
import { pct } from "@/lib/scale";

const CORPUS_DISTRICTS = 165;

function languageMeta() {
  const path = join(process.cwd(), "public", "languages.json");
  if (!existsSync(path)) return { supported: {} as Record<string, boolean> };
  return JSON.parse(readFileSync(path, "utf8")) as { supported: Record<string, boolean> };
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="serif tabular text-3xl text-[var(--text)]">{value}</div>
      <div className="mt-0.5 text-sm text-[var(--muted)]">{label}</div>
    </div>
  );
}

export default function Home() {
  const results = loadResults();
  const topology = loadTopology();
  const unmapped = loadUnmapped();
  const calibration = loadCalibration() as
    | { district_mean?: number; district_std?: number; inter_annotator_wer?: number }
    | null;
  const { supported } = languageMeta();

  const total = Object.keys(supported).length;
  const unsupported = Object.values(supported).filter((v) => !v).length;
  const measuredDistricts = new Set(
    results.runs.flatMap((r) => r.by_district.map((a) => a.key[0])),
  ).size;

  return (
    <main id="main" className="mx-auto max-w-6xl px-6 py-16 sm:py-24">
      <header className="mb-16 max-w-[65ch]">
        <h1 className="text-5xl sm:text-6xl">kya bola?</h1>
        <p className="mt-5 text-lg leading-relaxed text-[var(--muted)]">
          Every speech recognition vendor publishes one accuracy number per
          language. Hindi in Delhi and Hindi in Araria are not the same problem,
          and one number hides the difference. This measures it district by
          district.
        </p>
        {total > 0 && (
          <p className="mt-4 text-lg leading-relaxed text-[var(--muted)]">
            It also asks something nobody has published an answer to. The corpus
            behind this holds {total} languages. Commercial speech APIs
            officially support {total - unsupported}. Here is what happens to the
            other {unsupported}.
          </p>
        )}

        <div className="mt-10 grid grid-cols-2 gap-6 border-t border-[var(--border)] pt-6 sm:grid-cols-4">
          <Stat value={String(total || "—")} label="languages in the corpus" />
          <Stat value={String(unsupported || "—")} label="with no API support" />
          <Stat value={`${measuredDistricts}`} label="districts measured" />
          <Stat
            value={calibration?.inter_annotator_wer ? pct(calibration.inter_annotator_wer) : "—"}
            label="human disagreement floor"
          />
        </div>
      </header>

      <section className="mb-20" aria-labelledby="map-heading">
        <h2 id="map-heading" className="mb-1.5 text-3xl">The map</h2>
        <p className="mb-8 max-w-[65ch] text-[var(--muted)]">
          Error rate per district. Greener is better. Grey is not a gap in the
          measurement: Project Vaani has recorded {CORPUS_DISTRICTS} of
          India&rsquo;s districts so far, and the rest of the country has no
          transcribed audio in this corpus to score against.
        </p>
        <Explorer
          topology={topology}
          runs={results.runs}
          unmapped={unmapped}
          corpusDistricts={CORPUS_DISTRICTS}
        />
      </section>

      {results.runs.length > 0 && (
        <section className="mb-20" aria-labelledby="gap-heading">
          <h2 id="gap-heading" className="mb-1.5 text-3xl">The coverage gap</h2>
          <p className="mb-8 max-w-[65ch] text-[var(--muted)]">
            Languages an API does not claim to support are still sent to it, with
            language detection on. A refusal or an empty answer counts as a failed
            clip, because that is what a developer building for those speakers
            would experience.
          </p>
          <CoverageTable runs={results.runs} supported={supported} />
        </section>
      )}

      {calibration && (
        <section className="mb-20 max-w-[65ch]" aria-labelledby="trust-heading">
          <h2 id="trust-heading" className="mb-1.5 text-3xl">Is this trustworthy?</h2>
          <p className="mb-6 text-[var(--muted)]">
            Before measuring anything new, this harness reproduced a published
            result. The Vaani team benchmarked Sarvam Saaras v3 on their own Hindi
            evaluation set and reported a district mean word error rate of 18.3%
            with a standard deviation of 4.6. Running their clips through this
            pipeline gives:
          </p>
          <dl className="divide-y divide-[var(--border)] rounded-lg border border-[var(--border)] bg-[var(--surface)]">
            <div className="flex justify-between gap-4 px-5 py-3.5">
              <dt className="text-[var(--muted)]">district mean, ours</dt>
              <dd className="tabular font-medium">
                {pct(calibration.district_mean)}
                {calibration.district_std != null &&
                  ` ± ${(calibration.district_std * 100).toFixed(1)}`}
              </dd>
            </div>
            <div className="flex justify-between gap-4 px-5 py-3.5">
              <dt className="text-[var(--muted)]">district mean, published</dt>
              <dd className="tabular font-medium">18.3% ± 4.6</dd>
            </div>
            <div className="flex justify-between gap-4 px-5 py-3.5">
              <dt className="text-[var(--muted)]">two humans, same audio</dt>
              <dd className="tabular font-medium">{pct(calibration.inter_annotator_wer)}</dd>
            </div>
          </dl>
          <p className="mt-4 text-sm leading-relaxed text-[var(--muted)]">
            That last row is the floor. Two people transcribing the same audio
            disagree by that much, so no model can score below it and no gap
            narrower than it is a real difference between two systems.
          </p>
        </section>
      )}

      <footer className="max-w-[65ch] border-t border-[var(--border)] pt-8 text-sm leading-relaxed text-[var(--muted)]">
        <p>
          Built on{" "}
          <a
            className="underline decoration-[var(--border)] underline-offset-4 transition-colors duration-200 hover:text-[var(--text)]"
            href="https://huggingface.co/datasets/ARTPARK-IISc/Vaani"
          >
            Project Vaani
          </a>{" "}
          by ARTPARK and IISc, used under CC-BY-4.0. Method, caveats and every
          test in the{" "}
          <a
            className="underline decoration-[var(--border)] underline-offset-4 transition-colors duration-200 hover:text-[var(--text)]"
            href="https://github.com/reetbatra/kya-bola"
          >
            repository
          </a>
          .
        </p>
        <p className="mt-3">
          Audio is spontaneous, image-prompted speech recorded in real conditions,
          not read speech in a studio. Error rates here are legitimately higher
          than the numbers vendors publish on clean benchmarks. That is the point.
        </p>
      </footer>
    </main>
  );
}

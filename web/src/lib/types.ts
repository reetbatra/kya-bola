export type Aggregate = {
  key: string[];
  provider: string;
  clips: number;
  scored: number;
  excluded: number;
  wer: number | null;
  cer: number | null;
  primary_metric: "wer" | "cer";
  primary: number | null;
  empty_rate: number;
  low_confidence: boolean;
};

export type ProviderRun = {
  provider: string;
  clips: number;
  scored: number;
  excluded: number;
  empty: number;
  by_language: Aggregate[];
  by_district: Aggregate[];
  by_language_district: Aggregate[];
  district_mean_wer: number | null;
  district_std_wer: number | null;
};

export type Results = { runs: ProviderRun[] };

/** The Vaani team measured 10-15% WER between independent human transcribers
 *  of the same audio. Differences smaller than this are not real. */
export const HUMAN_FLOOR = { low: 0.1, high: 0.15 } as const;

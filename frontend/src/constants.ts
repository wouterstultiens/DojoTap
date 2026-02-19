import type { CountProfile, TimerProfile } from "./types";

export const DEFAULT_COUNT_PROFILE_ID = "count_default_legacy_increment";
export const DEFAULT_TIMER_PROFILE_ID = "time_default_existing";
export const POLGAR_COUNT_PROFILE_ID = "count_polgar_next_30_absolute";

function range(start: number, end: number, step = 1): number[] {
  const values: number[] = [];
  for (let number = start; number <= end; number += step) {
    values.push(number);
  }
  return values;
}

export function normalizeNumericValues(values: number[]): number[] {
  return Array.from(
    new Set(values.map((value) => Math.trunc(value)).filter((value) => value > 0))
  ).sort((left, right) => left - right);
}

export const LEGACY_COUNT_OPTIONS = (() => {
  const values: number[] = [];
  values.push(...range(1, 30, 1));
  values.push(...range(35, 100, 5));
  values.push(125, 150, 175, 200, 250, 300, 400, 500);
  return normalizeNumericValues(values);
})();

export const DEFAULT_MINUTE_OPTIONS = [
  5, 10, 15, 20, 25, 30, 40, 45, 60, 75, 90, 105, 120, 150, 180,
];

export const BUILTIN_COUNT_PROFILES: CountProfile[] = [
  {
    id: DEFAULT_COUNT_PROFILE_ID,
    kind: "count",
    name: "Default Increment",
    source: "builtin",
    mode: "increment",
    values: LEGACY_COUNT_OPTIONS,
  },
  {
    id: POLGAR_COUNT_PROFILE_ID,
    kind: "count",
    name: "Polgar M2 Next 30",
    source: "builtin",
    mode: "absolute",
    values: [],
  },
  {
    id: "count_study_chapters_1_30_absolute",
    kind: "count",
    name: "Study Chapters 1-30",
    source: "builtin",
    mode: "absolute",
    values: range(1, 30, 1),
  },
  {
    id: "count_classical_1_7_plus_60_180_absolute",
    kind: "count",
    name: "Classical 1-7 + 60-180",
    source: "builtin",
    mode: "absolute",
    values: normalizeNumericValues([...range(1, 7, 1), ...range(60, 180, 5)]),
  },
];

export const BUILTIN_TIMER_PROFILES: TimerProfile[] = [
  {
    id: DEFAULT_TIMER_PROFILE_ID,
    kind: "timer",
    name: "Default Time Mix",
    source: "builtin",
    values: DEFAULT_MINUTE_OPTIONS,
  },
  {
    id: "time_every_5_to_180",
    kind: "timer",
    name: "Every 5m to 180",
    source: "builtin",
    values: range(5, 180, 5),
  },
  {
    id: "time_classical_60_180_step5",
    kind: "timer",
    name: "Classical 60-180",
    source: "builtin",
    values: range(60, 180, 5),
  },
];

export function formatMinuteLabel(minutes: number): string {
  if (minutes < 60) {
    return `${minutes}m`;
  }

  const hours = Math.floor(minutes / 60);
  const minutesRemainder = minutes % 60;
  if (minutesRemainder === 0) {
    return `${hours}h`;
  }
  return `${hours}h${minutesRemainder}`;
}

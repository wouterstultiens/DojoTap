import type { CountLabelMode, TileSizeMode } from "./types";

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

export const MIN_COUNT_CAP = 1;
export const MAX_COUNT_CAP = 200;
export const COUNT_CAP_OPTIONS = range(MIN_COUNT_CAP, MAX_COUNT_CAP, 1);
export const DEFAULT_COUNT_CAP = 10;
export const DEFAULT_COUNT_LABEL_MODE: CountLabelMode = "increment";
export const DEFAULT_TILE_SIZE_MODE: TileSizeMode = "large";

export const TIMER_OPTIONS = range(5, 180, 5);

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

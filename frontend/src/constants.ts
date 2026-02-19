export const COUNT_OPTIONS = (() => {
  const values: number[] = [];
  for (let number = 1; number <= 30; number += 1) {
    values.push(number);
  }
  for (let number = 35; number <= 100; number += 5) {
    values.push(number);
  }
  values.push(125, 150, 175, 200, 250, 300, 400, 500);
  return Array.from(new Set(values)).sort((left, right) => left - right);
})();

export const MINUTE_OPTIONS = [
  5, 10, 15, 20, 25, 30, 40, 45, 60, 75, 90, 105, 120, 150, 180,
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


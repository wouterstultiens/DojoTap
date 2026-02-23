export type DiagnosticPhase = "point" | "start" | "end" | "error";

type DiagnosticDetails = Record<string, unknown>;

export interface DiagnosticEntry {
  id: number;
  sessionId: string;
  phase: DiagnosticPhase;
  event: string;
  timestampMs: number;
  isoTimestamp: string;
  relativeMs: number;
  durationMs?: number;
  details?: DiagnosticDetails;
}

interface DiagnosticsWindowApi {
  getLogs: () => DiagnosticEntry[];
  clearLogs: () => void;
  printRecent: (limit?: number) => void;
}

const LOG_PREFIX = "[DojoTapPerf]";
const STORAGE_KEY = "dojotap_perf_logs_v1";
const MAX_LOG_ENTRIES = 2500;
const SESSION_ID = `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
const sessionStartTime = performance.now();

let initialized = false;
let fetchWrapped = false;

function restoreEntries(): DiagnosticEntry[] {
  let raw: string | null = null;
  try {
    raw = localStorage.getItem(STORAGE_KEY);
  } catch {
    return [];
  }
  if (!raw) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed
      .filter((item): item is DiagnosticEntry => {
        return (
          Boolean(item) &&
          typeof item === "object" &&
          typeof (item as Partial<DiagnosticEntry>).id === "number" &&
          typeof (item as Partial<DiagnosticEntry>).sessionId === "string" &&
          typeof (item as Partial<DiagnosticEntry>).phase === "string" &&
          typeof (item as Partial<DiagnosticEntry>).event === "string" &&
          typeof (item as Partial<DiagnosticEntry>).timestampMs === "number" &&
          typeof (item as Partial<DiagnosticEntry>).isoTimestamp === "string" &&
          typeof (item as Partial<DiagnosticEntry>).relativeMs === "number"
        );
      })
      .slice(-MAX_LOG_ENTRIES);
  } catch {
    return [];
  }
}

const entries: DiagnosticEntry[] = restoreEntries();
let nextEntryId = entries.length > 0 ? entries[entries.length - 1].id + 1 : 1;

function roundMs(value: number): number {
  return Math.round(value * 100) / 100;
}

function persistEntries(): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries.slice(-MAX_LOG_ENTRIES)));
  } catch {
    // Ignore storage failures.
  }
}

function sanitizeUnknown(value: unknown): unknown {
  if (value === null || value === undefined) {
    return value;
  }

  const primitiveType = typeof value;
  if (
    primitiveType === "string" ||
    primitiveType === "number" ||
    primitiveType === "boolean" ||
    primitiveType === "bigint"
  ) {
    return value;
  }

  if (value instanceof Error) {
    return {
      name: value.name,
      message: value.message,
      stack: value.stack,
    };
  }

  if (Array.isArray(value)) {
    return value.slice(0, 20).map((item) => sanitizeUnknown(item));
  }

  if (primitiveType === "object") {
    const objectEntries = Object.entries(value as Record<string, unknown>).slice(0, 40);
    const sanitized: Record<string, unknown> = {};
    for (const [key, rawItem] of objectEntries) {
      sanitized[key] = sanitizeUnknown(rawItem);
    }
    return sanitized;
  }

  return String(value);
}

function sanitizeDetails(details?: DiagnosticDetails): DiagnosticDetails | undefined {
  if (!details) {
    return undefined;
  }

  const sanitized: DiagnosticDetails = {};
  for (const [key, value] of Object.entries(details)) {
    sanitized[key] = sanitizeUnknown(value);
  }
  return sanitized;
}

function pushEntry(entry: DiagnosticEntry): void {
  entries.push(entry);
  if (entries.length > MAX_LOG_ENTRIES) {
    entries.splice(0, entries.length - MAX_LOG_ENTRIES);
  }
  persistEntries();
}

function formatConsolePrefix(entry: DiagnosticEntry): string {
  const durationLabel = typeof entry.durationMs === "number" ? ` ${entry.durationMs}ms` : "";
  return `${LOG_PREFIX} ${entry.phase.toUpperCase()} ${entry.event}${durationLabel}`;
}

function record(
  event: string,
  phase: DiagnosticPhase,
  details?: DiagnosticDetails,
  durationMs?: number
): DiagnosticEntry {
  const entry: DiagnosticEntry = {
    id: nextEntryId,
    sessionId: SESSION_ID,
    phase,
    event,
    timestampMs: Date.now(),
    isoTimestamp: new Date().toISOString(),
    relativeMs: roundMs(performance.now() - sessionStartTime),
    ...(typeof durationMs === "number" ? { durationMs: roundMs(durationMs) } : {}),
    ...(details ? { details: sanitizeDetails(details) } : {}),
  };

  nextEntryId += 1;
  pushEntry(entry);

  const prefix = formatConsolePrefix(entry);
  if (entry.details) {
    console.log(prefix, entry.details);
  } else {
    console.log(prefix);
  }

  return entry;
}

export function logPoint(event: string, details?: DiagnosticDetails): void {
  record(event, "point", details);
}

export function logError(event: string, details?: DiagnosticDetails): void {
  record(event, "error", details);
}

export function startTimer(
  event: string,
  details?: DiagnosticDetails
): (endDetails?: DiagnosticDetails) => void {
  const startedAt = performance.now();
  record(event, "start", details);

  return (endDetails?: DiagnosticDetails) => {
    const durationMs = performance.now() - startedAt;
    record(event, "end", endDetails, durationMs);
  };
}

export function timeSync<T>(
  event: string,
  operation: () => T,
  details?: DiagnosticDetails
): T {
  const finish = startTimer(event, details);
  try {
    const result = operation();
    finish();
    return result;
  } catch (error) {
    finish({ failed: true, error: sanitizeUnknown(error) });
    throw error;
  }
}

export async function timeAsync<T>(
  event: string,
  operation: () => Promise<T>,
  details?: DiagnosticDetails
): Promise<T> {
  const finish = startTimer(event, details);
  try {
    const result = await operation();
    finish();
    return result;
  } catch (error) {
    finish({ failed: true, error: sanitizeUnknown(error) });
    throw error;
  }
}

export function getDiagnosticLogs(): DiagnosticEntry[] {
  return [...entries];
}

export function clearDiagnosticLogs(): void {
  entries.length = 0;
  nextEntryId = 1;
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore storage failures.
  }
  logPoint("diagnostics.cleared");
}

function requestUrlFromInput(input: RequestInfo | URL): string {
  if (typeof input === "string") {
    return input;
  }
  if (input instanceof URL) {
    return input.toString();
  }
  return input.url;
}

function methodFromRequest(input: RequestInfo | URL, init?: RequestInit): string {
  if (init?.method) {
    return init.method.toUpperCase();
  }
  if (input instanceof Request) {
    return input.method.toUpperCase();
  }
  return "GET";
}

function wrapFetchWithDiagnostics(): void {
  if (fetchWrapped) {
    return;
  }
  fetchWrapped = true;

  const originalFetch = window.fetch.bind(window);

  window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = requestUrlFromInput(input);
    const method = methodFromRequest(input, init);
    const finish = startTimer("network.fetch", { method, url });

    try {
      const response = await originalFetch(input, init);
      finish({
        method,
        url,
        status: response.status,
        ok: response.ok,
        redirected: response.redirected,
        type: response.type,
      });
      return response;
    } catch (error) {
      finish({
        method,
        url,
        failed: true,
        error: sanitizeUnknown(error),
      });
      throw error;
    }
  };
}

function attachLifecycleDiagnostics(): void {
  logPoint("lifecycle.readyState", { readyState: document.readyState });

  window.addEventListener("load", () => {
    logPoint("lifecycle.window.load");
    captureNavigationTiming();
  });

  window.addEventListener("pageshow", (event) => {
    logPoint("lifecycle.window.pageshow", { persisted: event.persisted });
  });

  window.addEventListener("beforeunload", () => {
    logPoint("lifecycle.window.beforeunload");
  });

  window.addEventListener("online", () => {
    logPoint("lifecycle.window.online");
  });

  window.addEventListener("offline", () => {
    logPoint("lifecycle.window.offline");
  });

  document.addEventListener("visibilitychange", () => {
    logPoint("lifecycle.document.visibilitychange", {
      visibilityState: document.visibilityState,
    });
  });

  window.addEventListener("error", (event) => {
    logError("window.error", {
      message: event.message,
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno,
      error: sanitizeUnknown(event.error),
    });
  });

  window.addEventListener("unhandledrejection", (event) => {
    logError("window.unhandledrejection", {
      reason: sanitizeUnknown(event.reason),
    });
  });
}

function captureNavigationTiming(): void {
  const navigationEntry = performance.getEntriesByType("navigation")[0];
  if (!navigationEntry) {
    return;
  }

  const navigation = navigationEntry as PerformanceNavigationTiming;
  logPoint("performance.navigation", {
    type: navigation.type,
    durationMs: roundMs(navigation.duration),
    dnsMs: roundMs(navigation.domainLookupEnd - navigation.domainLookupStart),
    connectMs: roundMs(navigation.connectEnd - navigation.connectStart),
    ttfbMs: roundMs(navigation.responseStart - navigation.requestStart),
    responseMs: roundMs(navigation.responseEnd - navigation.responseStart),
    domInteractiveMs: roundMs(navigation.domInteractive),
    domContentLoadedMs: roundMs(navigation.domContentLoadedEventEnd),
    loadEventMs: roundMs(navigation.loadEventEnd),
    transferSize: navigation.transferSize,
    encodedBodySize: navigation.encodedBodySize,
    decodedBodySize: navigation.decodedBodySize,
  });
}

function attachResourceObserver(): void {
  if (!("PerformanceObserver" in window)) {
    logPoint("performance.resource.unsupported");
    return;
  }

  const observer = new PerformanceObserver((list) => {
    for (const rawEntry of list.getEntries()) {
      const entry = rawEntry as PerformanceResourceTiming;
      logPoint("performance.resource", {
        name: entry.name,
        initiatorType: entry.initiatorType,
        durationMs: roundMs(entry.duration),
        transferSize: entry.transferSize,
        encodedBodySize: entry.encodedBodySize,
        decodedBodySize: entry.decodedBodySize,
        renderBlockingStatus:
          "renderBlockingStatus" in entry
            ? (entry as PerformanceResourceTiming & { renderBlockingStatus?: string })
                .renderBlockingStatus ?? null
            : null,
      });
    }
  });

  try {
    observer.observe({ type: "resource", buffered: true });
  } catch {
    observer.observe({ entryTypes: ["resource"] });
  }
}

function attachWindowApi(): void {
  const diagnosticsApi: DiagnosticsWindowApi = {
    getLogs: () => getDiagnosticLogs(),
    clearLogs: () => clearDiagnosticLogs(),
    printRecent: (limit = 100) => {
      const recent = entries.slice(-Math.max(1, Math.min(limit, MAX_LOG_ENTRIES)));
      console.table(recent);
    },
  };

  window.dojoTapPerf = diagnosticsApi;
}

export function initDiagnostics(): void {
  if (initialized) {
    return;
  }

  initialized = true;
  attachWindowApi();
  wrapFetchWithDiagnostics();
  attachLifecycleDiagnostics();
  attachResourceObserver();

  logPoint("diagnostics.init", {
    sessionId: SESSION_ID,
    location: window.location.href,
    userAgent: navigator.userAgent,
  });

  if (document.readyState === "complete") {
    captureNavigationTiming();
  }
}

declare global {
  interface Window {
    dojoTapPerf?: DiagnosticsWindowApi;
  }
}

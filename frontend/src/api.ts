import type {
  AuthStatusResponse,
  BootstrapResponse,
  LoginRequest,
  PreferencesResponse,
  PreferencesUpdateRequest,
  SubmitProgressRequest,
  SubmitProgressResponse,
} from "./types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/+$/, "") ?? "";
const SESSION_HEADER_NAME = "X-DojoTap-Session";
const SESSION_STORAGE_KEY = "dojotap_session_fallback_v1";

function apiUrl(path: string): string {
  return API_BASE_URL ? `${API_BASE_URL}${path}` : path;
}

const BOOTSTRAP_TIMEOUT_MS = 10_000;

function readSessionFallbackId(): string {
  return localStorage.getItem(SESSION_STORAGE_KEY)?.trim() ?? "";
}

function persistSessionFallbackId(response: Response): void {
  const sessionId = response.headers.get(SESSION_HEADER_NAME)?.trim() ?? "";
  if (sessionId) {
    localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  }
}

function clearSessionFallbackId(): void {
  localStorage.removeItem(SESSION_STORAGE_KEY);
}

function withSessionFallbackHeader(headersInit?: HeadersInit): Headers {
  const headers = new Headers(headersInit);
  const sessionId = readSessionFallbackId();
  if (sessionId) {
    headers.set(SESSION_HEADER_NAME, sessionId);
  }
  return headers;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export class BootstrapTimeoutError extends Error {
  constructor(timeoutMs: number) {
    super(`Task fetch timed out after ${Math.floor(timeoutMs / 1000)} seconds.`);
    this.name = "BootstrapTimeoutError";
  }
}

async function parseApiError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    if (payload.detail) {
      return payload.detail;
    }
  } catch {
    // ignore parse errors and return status text fallback
  }
  return `${response.status} ${response.statusText}`;
}

async function assertOk(response: Response): Promise<void> {
  if (!response.ok) {
    throw new ApiError(response.status, await parseApiError(response));
  }
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  await assertOk(response);
  return (await response.json()) as T;
}

export async function fetchBootstrap(): Promise<BootstrapResponse> {
  const abortController = new AbortController();
  const timeoutId = setTimeout(() => abortController.abort(), BOOTSTRAP_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(apiUrl("/api/bootstrap"), {
      signal: abortController.signal,
      credentials: "include",
      headers: withSessionFallbackHeader(),
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new BootstrapTimeoutError(BOOTSTRAP_TIMEOUT_MS);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }

  return parseJsonResponse<BootstrapResponse>(response);
}

export async function fetchAuthStatus(): Promise<AuthStatusResponse> {
  const response = await fetch(apiUrl("/api/auth/status"), {
    credentials: "include",
    headers: withSessionFallbackHeader(),
  });
  return parseJsonResponse<AuthStatusResponse>(response);
}

export async function loginWithCredentials(payload: LoginRequest): Promise<AuthStatusResponse> {
  const response = await fetch(apiUrl("/api/auth/login"), {
    method: "POST",
    credentials: "include",
    headers: withSessionFallbackHeader({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  persistSessionFallbackId(response);
  return parseJsonResponse<AuthStatusResponse>(response);
}

export async function logoutAuth(): Promise<AuthStatusResponse> {
  const response = await fetch(apiUrl("/api/auth/logout"), {
    method: "POST",
    credentials: "include",
    headers: withSessionFallbackHeader(),
  });
  const parsed = await parseJsonResponse<AuthStatusResponse>(response);
  clearSessionFallbackId();
  return parsed;
}

export async function fetchPreferences(): Promise<PreferencesResponse> {
  const response = await fetch(apiUrl("/api/preferences"), {
    credentials: "include",
    headers: withSessionFallbackHeader(),
  });
  return parseJsonResponse<PreferencesResponse>(response);
}

export async function savePreferences(
  payload: PreferencesUpdateRequest
): Promise<PreferencesResponse> {
  const response = await fetch(apiUrl("/api/preferences"), {
    method: "PUT",
    credentials: "include",
    headers: withSessionFallbackHeader({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  return parseJsonResponse<PreferencesResponse>(response);
}

export async function submitProgress(
  payload: SubmitProgressRequest
): Promise<SubmitProgressResponse> {
  const response = await fetch(apiUrl("/api/progress"), {
    method: "POST",
    credentials: "include",
    headers: withSessionFallbackHeader({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  return parseJsonResponse<SubmitProgressResponse>(response);
}

import type {
  AuthStatusResponse,
  BootstrapResponse,
  LoginRequest,
  SubmitProgressRequest,
  SubmitProgressResponse,
} from "./types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/+$/, "") ?? "";

function apiUrl(path: string): string {
  return API_BASE_URL ? `${API_BASE_URL}${path}` : path;
}

const BOOTSTRAP_TIMEOUT_MS = 10_000;

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

export async function fetchBootstrap(): Promise<BootstrapResponse> {
  const abortController = new AbortController();
  const timeoutId = setTimeout(() => abortController.abort(), BOOTSTRAP_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(apiUrl("/api/bootstrap"), { signal: abortController.signal });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new BootstrapTimeoutError(BOOTSTRAP_TIMEOUT_MS);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }
  return (await response.json()) as BootstrapResponse;
}

export async function fetchAuthStatus(): Promise<AuthStatusResponse> {
  const response = await fetch(apiUrl("/api/auth/status"));
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }
  return (await response.json()) as AuthStatusResponse;
}

export async function loginWithCredentials(payload: LoginRequest): Promise<AuthStatusResponse> {
  const response = await fetch(apiUrl("/api/auth/login"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }
  return (await response.json()) as AuthStatusResponse;
}

export async function logoutAuth(): Promise<AuthStatusResponse> {
  const response = await fetch(apiUrl("/api/auth/logout"), { method: "POST" });
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }
  return (await response.json()) as AuthStatusResponse;
}

export async function submitProgress(
  payload: SubmitProgressRequest
): Promise<SubmitProgressResponse> {
  const response = await fetch(apiUrl("/api/progress"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }
  return (await response.json()) as SubmitProgressResponse;
}

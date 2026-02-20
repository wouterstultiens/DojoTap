import type {
  AuthStatusResponse,
  BootstrapResponse,
  LoginRequest,
  ManualTokenRequest,
  SubmitProgressRequest,
  SubmitProgressResponse,
} from "./types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/+$/, "") ?? "";

function apiUrl(path: string): string {
  return API_BASE_URL ? `${API_BASE_URL}${path}` : path;
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
  const response = await fetch(apiUrl("/api/bootstrap"));
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

export async function setManualToken(payload: ManualTokenRequest): Promise<AuthStatusResponse> {
  const response = await fetch(apiUrl("/api/auth/manual-token"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }
  return (await response.json()) as AuthStatusResponse;
}

export async function clearManualToken(): Promise<AuthStatusResponse> {
  const response = await fetch(apiUrl("/api/auth/manual-token"), { method: "DELETE" });
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

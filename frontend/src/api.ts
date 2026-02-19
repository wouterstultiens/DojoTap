import type {
  BootstrapResponse,
  SubmitProgressRequest,
  SubmitProgressResponse,
} from "./types";

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
  const response = await fetch("/api/bootstrap");
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }
  return (await response.json()) as BootstrapResponse;
}

export async function submitProgress(
  payload: SubmitProgressRequest
): Promise<SubmitProgressResponse> {
  const response = await fetch("/api/progress", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }
  return (await response.json()) as SubmitProgressResponse;
}


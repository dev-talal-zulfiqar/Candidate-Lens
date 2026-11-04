// Base URL for the CandidateLens backend API. Configured via VITE_API_BASE_URL
// so the frontend can point at different backends per environment without
// code changes. Falls back to the local development default.
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export interface HealthResponse {
  status: 'ok'
  database: 'ok' | 'error'
}

export class ApiError extends Error {
  readonly status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/health`)

  if (!response.ok) {
    throw new ApiError(
      `Health check failed with status ${response.status}`,
      response.status,
    )
  }

  return (await response.json()) as HealthResponse
}

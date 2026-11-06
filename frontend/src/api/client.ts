import axios from 'axios'

// Base URL for the CandidateLens backend API. Configured via VITE_API_BASE_URL
// so the frontend can point at different backends per environment without
// code changes. Falls back to the local development default.
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

// Without an explicit timeout, axios defaults to 0 (wait forever) — a
// backend hang would leave the UI stuck with no error ever surfacing
// (QA-011). 15s comfortably covers ordinary CRUD/list calls; the handful
// of synchronous batch endpoints (resume upload, requirement edit/re-run)
// override it per-call below since they can legitimately run long until
// they move to background processing.
const DEFAULT_TIMEOUT_MS = 15_000

const http = axios.create({ baseURL: API_BASE_URL, timeout: DEFAULT_TIMEOUT_MS })

export interface HealthResponse {
  status: 'ok'
  database: 'ok' | 'error'
}

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(message: string, status: number, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

function describeErrorDetail(detail: unknown): string | null {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) =>
        typeof item === 'object' && item !== null && 'msg' in item
          ? String((item as { msg: unknown }).msg)
          : null,
      )
      .filter((msg): msg is string => msg !== null)
    if (messages.length > 0) return messages.join('; ')
  }
  return null
}

export interface ApiRequestInit {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: string | FormData
  timeoutMs?: number
}

export async function apiRequest<T>(path: string, init?: ApiRequestInit): Promise<T> {
  // FormData bodies (file uploads) must NOT get an explicit Content-Type —
  // the browser needs to set its own multipart boundary. JSON bodies arrive
  // here already stringified (call sites use JSON.stringify), so they're
  // passed straight through as the request payload rather than re-parsed.
  const isJsonBody = typeof init?.body === 'string'

  try {
    const response = await http.request<T>({
      url: path,
      method: init?.method ?? 'GET',
      data: init?.body,
      headers: isJsonBody ? { 'Content-Type': 'application/json' } : undefined,
      timeout: init?.timeoutMs ?? DEFAULT_TIMEOUT_MS,
    })

    if (response.status === 204) {
      return undefined as T
    }
    return response.data
  } catch (error) {
    if (axios.isAxiosError(error)) {
      if (error.response) {
        const body = error.response.data as { detail?: unknown } | undefined
        const detail = body?.detail ?? body
        const message =
          describeErrorDetail(detail) ??
          `Request failed with status ${error.response.status}`
        throw new ApiError(message, error.response.status, detail)
      }
      throw new ApiError(error.message || 'Network error', 0)
    }
    throw error
  }
}

export async function fetchHealth(): Promise<HealthResponse> {
  return apiRequest<HealthResponse>('/api/health')
}

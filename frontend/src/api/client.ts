// In production the SPA and API live on different origins, so requests must be
// absolute. VITE_API_URL is baked in at build time (see Railway frontend service).
// Empty in dev, where the Vite proxy forwards relative /api paths to localhost:8000.
const API_BASE = import.meta.env.VITE_API_URL ?? ""

export class ApiError extends Error {
  status: number
  detail: string
  constructor(status: number, detail: string) {
    super(detail)
    this.name = "ApiError"
    this.status = status
    this.detail = detail
  }
}

export async function apiFetch(path: string, options: RequestInit = {}): Promise<unknown> {
  const token = localStorage.getItem("token")

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  }

  if (token) {
    headers["Authorization"] = `Bearer ${token}`
  }

  const response = await fetch(API_BASE + path, { ...options, headers })

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new ApiError(response.status, body.detail ?? response.statusText)
  }

  if (response.status === 204) return null
  return response.json()
}

export async function apiFetchFile(path: string, formData: FormData): Promise<unknown> {
  const token = localStorage.getItem("token")

  const headers: Record<string, string> = {}
  if (token) {
    headers["Authorization"] = `Bearer ${token}`
  }

  const response = await fetch(API_BASE + path, { method: "POST", headers, body: formData })

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new ApiError(response.status, body.detail ?? response.statusText)
  }

  if (response.status === 204) return null
  return response.json()
}

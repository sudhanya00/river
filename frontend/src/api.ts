// Thin client for the FastAPI backend. Responses never carry author ids or return dates.
import { accessToken, browserTimeZone, signOut, supabase } from './auth'

export type Me = { tz: string; free_catches: number; bonus_catches: number; writes_left: number; drifting: number }

export type CatchResult =
  | { type: 'message'; id: string; text: string; catch_number: number; from_river: boolean }
  | { type: 'reveal'; id: string; text: string; written_at: string; seen_count: number; notes: string[] }
  | { type: 'out_of_catches' }
  | { type: 'river_empty' }

export type Returned = {
  id: string
  text: string
  written_at: string
  returned_at: string
  seen_count: number
  notes: string[]
}

export type Yours = { drifting: number; returned: Returned[] }

export type ReturnOption = 'near' | 'any' | 'far'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const DEV_USER_KEY = 'river-dev-user'

// Dev builds only: a fake user sent as X-Dev-User, which the API accepts only in dev mode.
// Without Supabase configured it defaults to 'asha' so the core loop works with no setup.
export function devUser(): string {
  if (!import.meta.env.DEV) return ''
  const fallback = supabase ? '' : 'asha'
  try {
    return localStorage.getItem(DEV_USER_KEY) || fallback
  } catch {
    return fallback
  }
}

export function setDevUser(name: string) {
  try {
    if (name) localStorage.setItem(DEV_USER_KEY, name)
    else localStorage.removeItem(DEV_USER_KEY)
  } catch {
    /* private mode: falls back to the default user */
  }
}

export async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const tz = browserTimeZone()
  if (tz) headers['X-Timezone'] = tz // only used when the account is first created
  const token = await accessToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  else if (import.meta.env.DEV && devUser()) headers['X-Dev-User'] = devUser()

  let res: Response
  try {
    res = await fetch('/api' + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
  } catch {
    throw new ApiError(0, 'Couldn’t reach the river. Check your connection and try again.')
  }
  if (res.status === 204) return undefined as T
  const data = await res.json().catch(() => null)
  if (res.status === 401 && token) await signOut() // expired or revoked: back to the sign-in screen
  if (!res.ok) {
    const detail = typeof data?.detail === 'string' ? data.detail : 'Something went wrong. Try again.'
    throw new ApiError(res.status, detail)
  }
  return data as T
}

export const api = {
  me: () => call<Me>('GET', '/me'),
  catch: () => call<CatchResult>('POST', '/catch'),
  write: (text: string, return_option: ReturnOption) => call<{ id: string }>('POST', '/messages', { text, return_option }),
  note: (id: string, note: string) => call<void>('POST', `/messages/${id}/note`, { note }),
  report: (id: string) => call<void>('POST', `/messages/${id}/report`),
  keep: (id: string) => call<void>('POST', `/messages/${id}/keep`),
  yours: () => call<Yours>('GET', '/yours'),
}

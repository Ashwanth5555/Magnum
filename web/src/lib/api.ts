const BASE = ''

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(BASE + path, {
    ...init,
    headers: { 'content-type': 'application/json', ...(init?.headers || {}) },
  })
  if (!r.ok) throw new Error(`${r.status} ${path}: ${(await r.text()).slice(0, 200)}`)
  return r.json() as Promise<T>
}
export const get = <T,>(p: string) => req<T>(p)
export const post = <T,>(p: string, body: unknown) =>
  req<T>(p, { method: 'POST', body: JSON.stringify(body) })

export const qs = (o: Record<string, any>) =>
  Object.entries(o)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
    .join('&')

/** Fire-and-forget instrumentation. A dropped beacon must never break a screen. */
export function track(events: Record<string, any>[]) {
  post('/api/events', { events }).catch(() => {})
}

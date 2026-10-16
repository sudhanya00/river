// Phase 2 replaces this with the user's own time zone from /me.
const TZ = 'Asia/Kolkata'

export const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', timeZone: TZ })

export const ordinal = (n: number) => {
  const s = ['th', 'st', 'nd', 'rd']
  const v = n % 100
  return n + (s[(v - 20) % 10] || s[v] || s[0])
}

export const plural = (n: number, one: string, many: string) => (n === 1 ? one : many)

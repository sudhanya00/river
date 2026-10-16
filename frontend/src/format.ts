// Dates show in the user's own zone (from /me), which is also where their daily refill happens.
let tz = 'Asia/Kolkata'

export function setTimeZone(zone: string) {
  try {
    new Intl.DateTimeFormat('en-IN', { timeZone: zone })
    tz = zone
  } catch {
    /* unknown zone: keep the default */
  }
}

export const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', timeZone: tz })

export const ordinal = (n: number) => {
  const s = ['th', 'st', 'nd', 'rd']
  const v = n % 100
  return n + (s[(v - 20) % 10] || s[v] || s[0])
}

export const plural = (n: number, one: string, many: string) => (n === 1 ? one : many)

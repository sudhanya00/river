// Dev-only: replaces the prototype's controls. Only rendered when import.meta.env.DEV, so it is
// stripped from production builds, and the backend refuses /api/dev/* unless RIVER_DEV_MODE is on.
import { useEffect, useState } from 'react'
import { ApiError, call, devUser, setDevUser } from './api'
import { signOut } from './auth'

type DevClock = { now: string; offset_days: number }

const dev = {
  forceDue: () => call<{ made_due: number }>('POST', '/dev/force-due'),
  refill: () => call<void>('POST', '/dev/refill'),
  clock: () => call<DevClock>('GET', '/dev/clock'),
  addDays: (add_days: number) => call<DevClock>('POST', '/dev/clock', { add_days }),
  resetClock: () => call<DevClock>('POST', '/dev/clock', { reset: true }),
}

// The server clock offset is global: every user (and every tab) sees the same moved time.
const SKIPS: { label: string; days: number }[] = [
  { label: '+1 day', days: 1 },
  { label: '+1 month', days: 30 },
  { label: '+1 year', days: 365 },
]

const fmtClock = (c: DevClock) =>
  new Date(c.now).toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) +
  (c.offset_days ? ` (+${Math.round(c.offset_days)} days)` : ' (real time)')

type Props = { email: string | null; onChanged: () => void; toast: (m: string) => void }

export default function DevPanel({ email, onChanged, toast }: Props) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState(devUser() || 'asha')
  const [clock, setClock] = useState<DevClock | null>(null)

  useEffect(() => {
    if (!open) return
    dev.clock().then(setClock, () => setClock(null))
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  const run = async (fn: () => Promise<string>) => {
    try {
      toast(await fn())
      onChanged()
    } catch (e) {
      toast(e instanceof ApiError ? e.message : String(e))
    }
  }

  const moveClock = (fn: () => Promise<DevClock>) =>
    run(async () => {
      const c = await fn()
      setClock(c)
      return `Server time is now ${fmtClock(c)}.`
    })

  const switchUser = async () => {
    const n = name.trim().toLowerCase()
    if (!n) return
    await signOut() // a Supabase session would otherwise take precedence over the dev header
    setDevUser(n)
    location.reload()
  }

  const leave = async () => {
    await signOut()
    setDevUser('')
    location.reload()
  }

  return (
    <>
      <button className="dev-btn" onClick={() => setOpen(true)}>Dev: {email ?? devUser()}</button>
      {open && (
        <div className="sheet" onClick={(e) => e.target === e.currentTarget && setOpen(false)}>
          <div className="sheet-in" role="dialog" aria-modal="true" aria-labelledby="devTitle">
            <h2 id="devTitle">Dev controls</h2>
            <p className="small">
              Not part of the app. {email ? `Signed in with Supabase as ${email}.` : `Fake user “${devUser()}” (X-Dev-User).`}
            </p>
            <div className="dev-row">
              <input aria-label="Dev user name" value={name} onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && switchUser()} />
              <button className="btn" onClick={switchUser}>Use fake user</button>
              <button className="btn" onClick={leave}>Sign out</button>
            </div>

            <h2 style={{ marginTop: 18 }}>Clock</h2>
            <p className="small dev-clock">{clock ? fmtClock(clock) : 'Loading server time…'}</p>
            <div className="dev-row">
              {SKIPS.map((s) => (
                <button key={s.days} className="btn" onClick={() => moveClock(() => dev.addDays(s.days))}>{s.label}</button>
              ))}
              <button className="btn" disabled={!clock?.offset_days} onClick={() => moveClock(dev.resetClock)}>Back to real time</button>
            </div>

            <h2 style={{ marginTop: 18 }}>Shortcuts</h2>
            <div className="dev-row">
              <button className="btn" onClick={() => run(async () => {
                const { made_due } = await dev.forceDue()
                return made_due ? `${made_due} message${made_due === 1 ? '' : 's'} due now. Catch to see.` : 'Nothing of yours is drifting.'
              })}>Make my messages due</button>
              <button className="btn" onClick={() => run(async () => { await dev.refill(); return 'Catches and writes refilled.' })}>
                Refill catches and writes
              </button>
            </div>
            <div className="actions">
              <span />
              <button className="btn solid" onClick={() => setOpen(false)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

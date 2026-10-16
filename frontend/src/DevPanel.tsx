// Dev-only: replaces the prototype's controls. Only rendered when import.meta.env.DEV, so it is
// stripped from production builds, and the backend refuses /api/dev/* unless RIVER_DEV_MODE is on.
import { useEffect, useState } from 'react'
import { ApiError, call, devUser, setDevUser } from './api'

const dev = {
  forceDue: () => call<{ made_due: number }>('POST', '/dev/force-due'),
  refill: () => call<void>('POST', '/dev/refill'),
}

type Props = { onChanged: () => void; toast: (m: string) => void }

export default function DevPanel({ onChanged, toast }: Props) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState(devUser())

  useEffect(() => {
    if (!open) return
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

  const switchUser = () => {
    const n = name.trim().toLowerCase()
    if (!n) return
    setDevUser(n)
    location.reload()
  }

  return (
    <>
      <button className="dev-btn" onClick={() => setOpen(true)}>Dev: {devUser()}</button>
      {open && (
        <div className="sheet" onClick={(e) => e.target === e.currentTarget && setOpen(false)}>
          <div className="sheet-in" role="dialog" aria-modal="true" aria-labelledby="devTitle">
            <h2 id="devTitle">Dev controls</h2>
            <p className="small">Not part of the app. Fake sign-in and shortcuts for testing the core loop.</p>
            <div className="dev-row">
              <input aria-label="Dev user name" value={name} onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && switchUser()} />
              <button className="btn" onClick={switchUser}>Switch user</button>
            </div>
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

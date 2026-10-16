import { useCallback, useEffect, useRef, useState } from 'react'
import { api, devUser, type Me } from './api'
import { useSession } from './auth'
import AuthView from './AuthView'
import DevPanel from './DevPanel'
import { setTimeZone } from './format'
import RiverView from './RiverView'
import WriteView from './WriteView'
import YoursView from './YoursView'

type View = 'river' | 'write' | 'yours'
const TABS: { v: View; label: string }[] = [
  { v: 'river', label: 'River' },
  { v: 'write', label: 'Write' },
  { v: 'yours', label: 'Yours' },
]

function useToast() {
  const [msg, setMsg] = useState('')
  const [show, setShow] = useState(false)
  const timer = useRef<number | undefined>(undefined)
  const toast = useCallback((m: string) => {
    setMsg(m)
    setShow(true)
    clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setShow(false), 2600)
  }, [])
  return { msg, show, toast }
}

export default function App() {
  const { ready, session } = useSession()
  if (!ready) return null
  if (!session && !devUser()) return <AuthView />
  // Keyed on the user so switching accounts starts from a clean slate.
  return <Signed key={session?.user.id ?? devUser()} email={session?.user.email ?? null} />
}

function Signed({ email }: { email: string | null }) {
  const [view, setView] = useState<View>('river')
  const [me, setMe] = useState<Me | null>(null)
  const { msg, show, toast } = useToast()

  const refreshMe = useCallback(() => {
    api.me().then((m) => {
      setTimeZone(m.tz)
      setMe(m)
    }, () => {})
  }, [])
  useEffect(refreshMe, [refreshMe])

  const go = (v: View) => {
    setView(v)
    window.scrollTo(0, 0)
  }

  const count = me
    ? `${me.free_catches} free catch${me.free_catches === 1 ? '' : 'es'} today${me.bonus_catches ? ` + ${me.bonus_catches} extra` : ''}`
    : ''

  return (
    <>
      <div className="app">
        <header className="top">
          <div className="mark">river</div>
          <div className="count">{count}</div>
          {import.meta.env.DEV && <DevPanel email={email} onChanged={refreshMe} toast={toast} />}
        </header>
        <main>
          {/* River stays mounted so a caught card survives a quick look at another tab. */}
          <div hidden={view !== 'river'}>
            <RiverView onChanged={refreshMe} toast={toast} goWrite={() => go('write')} />
          </div>
          {view === 'write' && <WriteView me={me} onChanged={refreshMe} />}
          {view === 'yours' && <YoursView email={email} goWrite={() => go('write')} toast={toast} />}
        </main>
      </div>

      <nav className="tabs" aria-label="Sections">
        <div className="inner" role="tablist">
          {TABS.map((t) => (
            <button key={t.v} className="tab" role="tab" aria-selected={view === t.v} onClick={() => go(t.v)}>
              {t.label}
            </button>
          ))}
        </div>
      </nav>
      <div className={'toast' + (show ? ' show' : '')} role="status" aria-live="polite">{msg}</div>
    </>
  )
}

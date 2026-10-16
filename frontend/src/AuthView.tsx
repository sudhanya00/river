import { useState } from 'react'
import { setDevUser } from './api'
import { sendMagicLink, signInWithGoogle, supabase } from './auth'

const INTRO_KEY = 'river-seen-intro'

function seenIntro(): boolean {
  try {
    return localStorage.getItem(INTRO_KEY) === '1'
  } catch {
    return false
  }
}

function markIntroSeen() {
  try {
    localStorage.setItem(INTRO_KEY, '1')
  } catch {
    /* private mode: the intro shows again next time, which is fine */
  }
}

// Supabase reports a failed link (expired, already used) as ?error=…&error_description=… or in the hash.
// Read it once and strip it from the address bar so a reload doesn't show it again.
function takeLinkError(): string {
  const params = new URLSearchParams(window.location.search)
  const hash = new URLSearchParams(window.location.hash.slice(1))
  const code = params.get('error_code') || hash.get('error_code')
  const desc = params.get('error_description') || hash.get('error_description')
  if (!code && !desc) return ''
  window.history.replaceState(null, '', window.location.pathname)
  if (code === 'otp_expired') return 'That sign-in link has expired or was already used. Send yourself a new one.'
  return desc || 'Sign-in didn’t work. Try again.'
}

const LINK_ERROR = takeLinkError()

const POINTS = [
  'Write a short message to a stranger and let it drift.',
  'Catch messages other people let go. You’ll only ever see each one once.',
  'Leave a note if one finds you. Only the person who wrote it will read it.',
  'One day, without warning, yours comes back to you.',
]

export default function AuthView() {
  const [step, setStep] = useState<'intro' | 'signin'>(seenIntro() || LINK_ERROR ? 'signin' : 'intro')
  const [email, setEmail] = useState('')
  const [sentTo, setSentTo] = useState('')
  const [err, setErr] = useState(LINK_ERROR)
  const [busy, setBusy] = useState(false)

  const run = async (fn: () => Promise<void>) => {
    setErr('')
    setBusy(true)
    try {
      await fn()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const sendLink = () => {
    const e = email.trim()
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e)) return setErr('Enter your email address.')
    run(async () => {
      await sendMagicLink(e)
      setSentTo(e)
    })
  }

  return (
    <div className="app">
      <header className="top"><div className="mark">river</div></header>
      <main className="auth">
        {step === 'intro' ? (
          <section aria-label="About River">
            <h1 className="h">Messages in a river</h1>
            <p className="sub">Like coins thrown into a river, but someone catches them.</p>
            <ul className="intro">{POINTS.map((p) => <li key={p}>{p}</li>)}</ul>
            <p className="small">No names, no profiles. Nobody ever sees who wrote what.</p>
            <button className="btn primary" onClick={() => { markIntroSeen(); setStep('signin') }}>Get started</button>
          </section>
        ) : sentTo ? (
          <section aria-label="Check your email">
            <h1 className="h">Check your email</h1>
            <p className="sub">We sent a sign-in link to {sentTo}. Open it in this browser to come back here signed in. Only the newest link works.</p>
            <button className="link" onClick={() => setSentTo('')}>Use a different email</button>
          </section>
        ) : (
          <section aria-label="Sign in">
            <h1 className="h">Sign in to start</h1>
            <p className="sub">Your messages can take years to come back. An account makes sure they find you, even on a new phone.</p>
            {supabase ? (
              <>
                <button className="btn primary" disabled={busy} onClick={() => run(signInWithGoogle)}>Continue with Google</button>
                <div className="or" aria-hidden="true"><span>or</span></div>
                <label htmlFor="email" className="small">Email</label>
                <input id="email" className="field" type="email" autoComplete="email" inputMode="email"
                  placeholder="you@example.com" value={email}
                  onChange={(e) => { setEmail(e.target.value); setErr('') }}
                  onKeyDown={(e) => e.key === 'Enter' && sendLink()} />
                <button className="btn primary" disabled={busy} onClick={sendLink}>Email me a sign-in link</button>
              </>
            ) : (
              <p className="err">Sign-in isn’t set up yet. Add VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY to frontend/.env.local.</p>
            )}
            <p className="err" role="alert">{err}</p>
            {import.meta.env.DEV && <DevSignIn />}
          </section>
        )}
      </main>
    </div>
  )
}

function DevSignIn() {
  const [name, setName] = useState('asha')
  const go = () => {
    const n = name.trim().toLowerCase()
    if (!n) return
    setDevUser(n)
    location.reload()
  }
  return (
    <div className="dev-row" style={{ marginTop: 28 }}>
      <input aria-label="Dev user name" value={name} onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && go()} />
      <button className="dev-btn" onClick={go}>Dev: continue as fake user</button>
    </div>
  )
}

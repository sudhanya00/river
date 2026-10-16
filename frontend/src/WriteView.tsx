import { useState } from 'react'
import { api, ApiError, type Me, type ReturnOption } from './api'
import { blocked } from './filter'

const WRITES_PER_DAY = 3

const OPTIONS: { value: ReturnOption; title: string; hint: string }[] = [
  { value: 'near', title: 'Near future', hint: 'Within a few months' },
  { value: 'any', title: 'Anytime', hint: 'Next month, or years from now' },
  { value: 'far', title: 'No time soon', hint: 'Years from now' },
]

type Props = { me: Me | null; onChanged: () => void }

export default function WriteView({ me, onChanged }: Props) {
  const [text, setText] = useState('')
  const [when, setWhen] = useState<ReturnOption>('any')
  const [err, setErr] = useState('')
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)

  const send = async () => {
    const t = text.trim()
    if (me && me.writes_left <= 0) return setErr('You’ve sent today’s messages. You can write more tomorrow.')
    if (t.length < 20) return setErr('Write at least 20 characters so it means something to whoever catches it.')
    const b = blocked(t)
    if (b) return setErr(b)
    setBusy(true)
    try {
      await api.write(t, when)
      setText('')
      setSent(true)
      onChanged()
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  if (sent) {
    return (
      <section className="view active" aria-label="Write">
        <div className="sent">
          <svg viewBox="0 0 90 60" aria-hidden="true">
            <g className="away"><path fill="var(--marigold)" d="M10 30 L50 30 L41 43 L19 43Z M23 30 L30 12 L37 30Z" /></g>
            <path d="M0 46 Q22 40 45 46 T90 46" fill="none" stroke="var(--water)" strokeWidth="3" />
          </svg>
          <h2 className="h">It's in the river now</h2>
          <p>You won't know when it comes back. Neither will we.</p>
          <button className="btn" onClick={() => { setSent(false); setErr('') }}>Write another</button>
        </div>
      </section>
    )
  }

  return (
    <section className="view active" aria-label="Write">
      <h1 className="h">Write to a stranger</h1>
      <p className="sub">Someone will catch this. One day, so will you.</p>
      <label htmlFor="msg" className="small">Your message</label>
      <textarea id="msg" maxLength={500} rows={7} placeholder="What do you want someone to read today?" value={text}
        onChange={(e) => { setText(e.target.value); setErr('') }} />
      <div className="row small">
        <span>{text.length} / 500</span>
        {me && <span>{me.writes_left} of {WRITES_PER_DAY} messages left today</span>}
      </div>
      <fieldset>
        <legend>When should it come back to you?</legend>
        <div className="opts">
          {OPTIONS.map((o) => (
            <label className="opt" key={o.value}>
              <input type="radio" name="when" value={o.value} checked={when === o.value} onChange={() => setWhen(o.value)} />
              <div><b>{o.title}</b><span>{o.hint}</span></div>
            </label>
          ))}
        </div>
      </fieldset>
      <p className="err">{err}</p>
      <button className="btn primary" onClick={send} disabled={busy}>Let it drift</button>
    </section>
  )
}

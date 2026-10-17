import { useRef, useState } from 'react'
import { api, ApiError, type CatchResult } from './api'
import { blocked } from './filter'
import { fmtDate, ordinal, plural } from './format'

type Stage = { type: 'idle' } | CatchResult

type Props = {
  onChanged: () => void
  toast: (m: string) => void
  goWrite: () => void
}

function Scene({ rippleRef }: { rippleRef: React.RefObject<SVGCircleElement | null> }) {
  return (
    <div className="scene" aria-hidden="true">
      <svg viewBox="0 0 400 190" preserveAspectRatio="xMidYMid slice">
        <g className="wave w2" opacity=".45"><path fill="var(--water)" d="M0 70 Q50 58 100 70 T200 70 T300 70 T400 70 T500 70 T600 70 T700 70 T800 70 V190 H0Z" /></g>
        <g transform="translate(0,62)"><g className="drift d2"><path fill="var(--boat)" d="M0 10 L26 10 L20 18 L6 18Z M9 10 L13 0 L17 10Z" /></g></g>
        <g transform="translate(0,74)"><g className="drift d4"><circle r="4" cx="0" cy="0" fill="var(--marigold)" /></g></g>
        <g className="wave" opacity=".7"><path fill="var(--water)" d="M0 100 Q50 86 100 100 T200 100 T300 100 T400 100 T500 100 T600 100 T700 100 T800 100 V190 H0Z" /></g>
        <g transform="translate(0,92)"><g className="drift"><path fill="var(--boat)" d="M0 12 L32 12 L25 22 L7 22Z M11 12 L16 0 L21 12Z" /></g></g>
        <g transform="translate(0,108)"><g className="drift d5"><circle r="5" cx="0" cy="0" fill="var(--marigold)" /></g></g>
        <circle ref={rippleRef} className="ripple" cx="200" cy="125" r="18" fill="none" stroke="var(--boat)" strokeWidth="2" />
        <g className="wave w3"><path fill="var(--water)" d="M0 130 Q50 118 100 130 T200 130 T300 130 T400 130 T500 130 T600 130 T700 130 T800 130 V190 H0Z" /></g>
        <g transform="translate(0,124)"><g className="drift d3"><path fill="var(--boat)" d="M0 12 L30 12 L24 21 L6 21Z M10 12 L15 1 L20 12Z" /></g></g>
      </svg>
    </div>
  )
}

function NoteBox({ id, toast }: { id: string; toast: (m: string) => void }) {
  const [note, setNote] = useState('')
  const [err, setErr] = useState('')
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)

  if (done) return <div className="note-box"><p className="small">Your note is tied to it now. Only the writer will ever read it.</p></div>

  const add = async () => {
    const v = note.trim()
    if (v.length < 2) return setErr('Write something first.')
    const b = blocked(v)
    if (b) return setErr(b)
    setBusy(true)
    try {
      await api.note(id, v)
      setDone(true)
      toast('Note added.')
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="note-box">
      <label htmlFor="note">Leave a note for the writer</label>
      <textarea id="note" maxLength={140} rows={2} placeholder="Something short" value={note}
        onChange={(e) => { setNote(e.target.value); setErr('') }} />
      <div className="row">
        <span className="small">Only the writer sees notes, if this ever drifts back to them.</span>
        <button className="btn" onClick={add} disabled={busy}>Add note</button>
      </div>
      <p className="err">{err}</p>
    </div>
  )
}

export default function RiverView({ onChanged, toast, goWrite }: Props) {
  const [stage, setStage] = useState<Stage>({ type: 'idle' })
  const [busy, setBusy] = useState(false)
  const rippleRef = useRef<SVGCircleElement>(null)

  const ripple = () => {
    const r = rippleRef.current
    if (!r) return
    r.classList.remove('go')
    void r.getBoundingClientRect()
    r.classList.add('go')
  }

  const catchOne = async () => {
    setBusy(true)
    try {
      const res = await api.catch()
      if (res.type === 'message' || res.type === 'reveal') ripple()
      setStage(res)
      onChanged()
    } catch (e) {
      toast(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const act = async (fn: () => Promise<unknown>, msg: string) => {
    try {
      await fn()
      setStage({ type: 'idle' })
      onChanged()
      toast(msg)
    } catch (e) {
      toast(e instanceof ApiError ? e.message : String(e))
    }
  }

  let card: React.ReactNode
  switch (stage.type) {
    case 'idle':
      card = <p className="hint">Messages from strangers drift by here. Each one you catch, you'll only ever see once.</p>
      break
    case 'message':
      card = (
        <article className={'letter unfold' + (stage.from_river ? ' from-river' : '')} key={stage.id}>
          {stage.from_river && <p className="from-river-tag">From the river</p>}
          <p className="msg">{stage.text}</p>
          <p className="meta">You're the {ordinal(stage.catch_number)} person to catch this.</p>
          {/* No one wrote a river message, so a note would never be read. */}
          {!stage.from_river && <NoteBox id={stage.id} toast={toast} />}
          <div className="actions">
            <button className="btn solid" onClick={() => setStage({ type: 'idle' })}>Let it go</button>
            <button className="link" onClick={() => act(() => api.report(stage.id), 'Reported. You won’t see this again.')}>Report</button>
          </div>
        </article>
      )
      break
    case 'reveal': {
      const n = stage.notes.length
      card = (
        <article className="letter reveal unfold" key={'r' + stage.id}>
          <h2>This one is yours</h2>
          <p className="msg">{stage.text}</p>
          <p className="stats">
            You wrote this on {fmtDate(stage.written_at)}. Since then, {stage.seen_count}{' '}
            {plural(stage.seen_count, 'person has', 'people have')} seen it and {n} {plural(n, 'left a note', 'left notes')}.
          </p>
          {n > 0 && <ul className="notes">{stage.notes.map((x, i) => <li key={i}>{x}</li>)}</ul>}
          <button className="btn solid" onClick={() => act(() => api.keep(stage.id), 'Kept. Find it under Yours.')}>Keep it</button>
        </article>
      )
      break
    }
    case 'out_of_catches':
      card = (
        <div className="calm">
          <h2>That's today's catches</h2>
          <p>Free catches refill tomorrow. You can also get more now.</p>
          <button className="btn solid" onClick={() => toast('Buying catches arrives in a later build.')}>Get 10 more catches</button>
          <div className="ad">Ad banner</div>
        </div>
      )
      break
    case 'river_empty':
      card = (
        <div className="calm">
          <h2>The river is calm</h2>
          <p>You've read every message in it for now. New ones drift in as people write. Leave one for someone else.</p>
          <button className="btn solid" onClick={goWrite}>Write a message</button>
          <div className="ad">Ad banner</div>
        </div>
      )
      break
  }

  return (
    <section className="view active" aria-label="River">
      <Scene rippleRef={rippleRef} />
      <button className="catch" onClick={catchOne} disabled={busy}>Catch a message</button>
      <div id="stage" aria-live="polite">{card}</div>
    </section>
  )
}

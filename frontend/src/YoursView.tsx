import { useEffect, useState } from 'react'
import { api, ApiError, type Yours } from './api'
import { fmtDate, plural } from './format'

type Props = { goWrite: () => void; toast: (m: string) => void }

export default function YoursView({ goWrite, toast }: Props) {
  const [data, setData] = useState<Yours | null>(null)

  useEffect(() => {
    api.yours().then(setData, (e) => toast(e instanceof ApiError ? e.message : String(e)))
  }, [toast])

  if (!data) return <section className="view active" aria-label="Yours"><h1 className="h">Yours</h1></section>

  const { drifting, returned } = data
  return (
    <section className="view active" aria-label="Yours">
      <h1 className="h">Yours</h1>
      {drifting > 0 ? (
        <>
          <p className="drifting">{drifting} {plural(drifting, 'message', 'messages')} drifting</p>
          <p className="sub">They'll come back when the river brings them. Even we won't tell you when.</p>
        </>
      ) : (
        <>
          <p className="sub">Nothing of yours in the river yet.</p>
          <button className="btn solid" onClick={goWrite}>Write a message</button>
        </>
      )}
      {returned.length > 0 && (
        <div className="kept">
          {returned.map((m) => (
            <article className="letter reveal" key={m.id}>
              <p className="msg">{m.text}</p>
              <p className="small">Written {fmtDate(m.written_at)}, came back {fmtDate(m.returned_at)}. Seen by {m.seen_count}.</p>
              {m.notes.length > 0 && (
                <details>
                  <summary>{m.notes.length} {plural(m.notes.length, 'note', 'notes')} from strangers</summary>
                  <ul className="notes" style={{ marginTop: 10 }}>{m.notes.map((x, i) => <li key={i}>{x}</li>)}</ul>
                </details>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

# River — Claude Code handoff

Working name: **River** (placeholder). A Lythhouse Labs project.

## Read this first

`river-prototype.html` (in this folder) is the **source of truth for look, feel, copy and behaviour**. Open it in a browser and play it before writing code. Port its design tokens, typography, river scene, card "unfold" animation and copy as closely as possible. Where this doc and the prototype disagree on behaviour, this doc wins; on visuals, the prototype wins.

The "Prototype" button and its controls (skip time, debug list of hidden return dates) are **testing tools only** and must not ship.

## The idea in one paragraph

People write short anonymous messages and drop them into a shared "river", like coins thrown into a river. Others catch messages one at a time and read them. Every message is seen at most once per person. Catchers can attach a short private note that only the author will ever see. Each message has a hidden return date; on some random day the author catches their own message back and sees: "You wrote this on 15 Oct 2026. Since then, 280 people have seen it and 10 left notes."

## Product rules (decided)

### Writing
- Message length: 20–500 characters.
- Limit: 3 messages per user per day.
- Author picks when it should come back. The exact date is random inside the range and is **never shown to the user or sent to the client**:

| Option | UI hint | Hidden range (days after writing) |
|---|---|---|
| Near future | Within a few months | 30–90 |
| Anytime | Next month, or years from now | 30–1095 |
| No time soon | Years from now | 730–1825 |

- 30 days is the cooling period: no message can return to its author before that. Keep all range numbers in config.
- Submissions pass the content filter (see Moderation).

### Catching
- Fixed number of free catches per day (prototype: 5; config). Refill at local midnight in the user's time zone (default Asia/Kolkata).
- Extra catches can be bought (bonus balance, spent after free catches).
- **No repeats**: once a user has seen a message, it never comes back to them.
- A user's own messages never appear in their random catches. They only come back through the return mechanism.
- Order of operations on every catch:
  1. If the user has an own message with `return_at <= now` that hasn't been returned, serve that as the reveal. **This does not use a catch** and works even with 0 catches left.
  2. Else if no catches left, return `out_of_catches`.
  3. Else pick a random message that is: not the user's, not seen by them, not hidden, active. If none, return `river_empty` (no catch spent).
  4. Record the catch, spend one catch, return the message.
- If a user is inactive on their return day, the message waits and is served on their next catch.
- The caught card shows "You're the Nth person to catch this."

### Notes
- After catching, a user may add one note per message, max 140 chars, filtered.
- Notes are visible **only to the author**, and only when the message returns. Other catchers never see notes.

### Return / reveal
- Reveal card: "This one is yours", the message, "You wrote this on {date}. Since then, {N} people have seen it and {M} left notes.", then the notes.
- "Keep it" marks it returned; it moves to the Yours tab.
- After returning, the message **stays in the river** for others to keep catching (confirm, see Open questions).

### Yours tab
- Shows only a count of messages still drifting. No dates, no text (the surprise depends on forgetting).
- Lists returned messages with written date, return date, seen count, and notes.

### Moderation (no paid APIs)
- Server-side filter on messages and notes (mirror on client for instant feedback):
  - Wordlist (start from the prototype list, keep in a config file, add Hindi/Hinglish terms).
  - Block phone numbers and email addresses (anonymity).
- Report button on caught messages. Reported message is hidden for the reporter immediately.
- Auto-hide a message after N unique reports (start with 3; config).
- Authors whose messages get auto-hidden lose bonus/free catch credits or get a temporary write cooldown (config; pick one in phase 4).
- Authors can report notes on their returned messages.
- Simple admin view: list hidden/reported items, restore or delete.

### Monetisation
- Buy extra catches (e.g. 10 for a small price). Web: Razorpay. Native later: Play Billing / StoreKit (check fees before pricing).
- Later options: keepsake export of returned messages with notes; longer return windows.
- Ad banners **only** on the "out of catches" and "river is calm" screens. Never on a message, reveal, or the write screen.

### Accounts
- Login required (Google sign-in + email magic link). Anonymous device IDs are not enough: losing a phone would lose all your returns.
- Author identity is **never exposed** to catchers. API responses for caught messages must not include author IDs.
- Account deletion removes the user's messages from the river and their notes.

### Privacy note
Messages are public-but-anonymous by design (strangers read them), so the thing to protect is the link between a message and its author, plus notes (private to the author). Encrypt notes at the application level if cheap to do; rely on the provider's encryption at rest for the rest.

## Recommended stack (low budget, confirm before starting)

- **Frontend:** React + Vite + TypeScript as an installable PWA. Ship on the web first to avoid app store fees; wrap with Capacitor later for Play Store / App Store.
- **Backend:** Python FastAPI (owner's strongest language).
- **Database + auth:** Supabase free tier (Postgres + Auth). Use Supabase only for Postgres and auth; all river logic lives in FastAPI so `return_at` and `author_id` never reach the client.
- **Hosting:** any cheap container host for FastAPI; static hosting for the PWA.
- **Longevity:** these promises last up to 5 years. Prepay the domain, schedule daily DB backups to separate storage, keep the stack boring.

## Data model (Postgres)

```sql
create table users (
  id uuid primary key,              -- from auth provider
  created_at timestamptz not null default now(),
  tz text not null default 'Asia/Kolkata',
  free_catches int not null default 5,
  free_refilled_on date not null default current_date,
  bonus_catches int not null default 0,
  writes_today int not null default 0,
  writes_counted_on date not null default current_date
);

create table messages (
  id uuid primary key default gen_random_uuid(),
  author_id uuid not null references users(id) on delete cascade,
  text text not null check (char_length(text) between 20 and 500),
  return_option text not null check (return_option in ('near','any','far')),
  created_at timestamptz not null default now(),
  return_at timestamptz not null,
  returned_at timestamptz,
  status text not null default 'active' check (status in ('active','hidden','deleted')),
  report_count int not null default 0,
  rand_key double precision not null default random()   -- for cheap random picks
);
create index on messages (status, rand_key);
create index on messages (author_id, return_at) where returned_at is null;

create table catches (
  user_id uuid not null references users(id) on delete cascade,
  message_id uuid not null references messages(id) on delete cascade,
  caught_at timestamptz not null default now(),
  note text check (note is null or char_length(note) between 2 and 140),
  noted_at timestamptz,
  primary key (user_id, message_id)   -- enforces no repeats
);
create index on catches (message_id);

create table reports (
  reporter_id uuid not null references users(id) on delete cascade,
  target_type text not null check (target_type in ('message','note')),
  target_id text not null,            -- message id, or message_id:user_id for a note
  created_at timestamptz not null default now(),
  primary key (reporter_id, target_type, target_id)
);

create table purchases (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id),
  provider text not null,
  provider_ref text not null unique,
  catches int not null,
  amount_paise int not null,
  created_at timestamptz not null default now()
);
```

Seen count for the reveal = `count(*) from catches where message_id = ?`. Notes = rows with non-null `note`.

**Random pick:** start with `rand_key >= random() order by rand_key limit k` plus an anti-join on `catches`, falling back to wrapping around from 0. Avoid `order by random()` once the table grows. Do the whole catch in one transaction.

## API (FastAPI)

All endpoints require auth. Responses never include `author_id` or `return_at`.

- `GET /me` → catches left (free, bonus), writes left today, count of drifting messages.
- `POST /catch` → one of:
  - `{type:"message", id, text, catch_number}`
  - `{type:"reveal", id, text, written_at, seen_count, notes:[...]}`
  - `{type:"out_of_catches"}`
  - `{type:"river_empty"}`
- `POST /messages/{id}/keep` → marks own returned message as kept.
- `POST /messages` `{text, return_option}` → 201, or 422 with a user-facing reason (too short, filtered, daily limit).
- `POST /messages/{id}/note` `{note}` → only if the user caught it and hasn't noted it.
- `POST /messages/{id}/report`
- `POST /notes/report` `{message_id, note_author_ref}` → for authors reporting a note on their returned message (don't expose the note author's real id; use an opaque ref).
- `GET /yours` → drifting count + returned messages with stats and notes.
- `POST /purchases/razorpay/order`, `POST /purchases/razorpay/webhook` → verify signature, add bonus catches idempotently.
- `DELETE /me` → delete account and content.
- Admin (role-gated): `GET /admin/reports`, `POST /admin/messages/{id}/restore|delete`.

## Screens (match the prototype)

1. **River:** animated river scene, "Catch a message" button, card area. States: idle hint, caught message (with note box, "Let it go", "Report"), reveal, out of catches (+ buy, + ad slot), river calm (+ write CTA, + ad slot).
2. **Write:** textarea with counter, writes-left counter, three return options as radio cards, "Let it drift", then the sent screen ("It's in the river now").
3. **Yours:** drifting count, returned messages with notes in a collapsible.
4. **Auth:** sign in with Google / email link. Short explainer on first open.
5. **Settings:** account deletion, data export, report history (later).

Keep: light and dark themes from the prototype tokens, `prefers-reduced-motion`, visible focus, safe-area handling on phones.

## Build phases

**Phase 1 — Core loop (local)**
FastAPI + Postgres via docker-compose, schema migrations (Alembic), write/catch/note/keep/yours endpoints, PWA screens ported from the prototype, fake auth for dev.
Done when: two dev users can write, catch each other's messages without repeats, and a forced-due message returns as a reveal with correct counts.

**Phase 2 — Real auth + timing**
Supabase Auth (Google + email link), per-user time zone daily refills, cooling period and range config, a dev-only clock override (replaces the prototype's skip-time buttons).

**Phase 3 — Moderation**
Wordlist + PII filter (shared module, tested), reports, auto-hide threshold, author penalty, admin page.

**Phase 4 — Money**
Razorpay bonus catches with webhook verification and idempotency, ad slots on the two allowed screens.

**Phase 5 — Launch prep**
Seed messages (start from the prototype's set, write more), backups, privacy policy, account deletion, PWA install, then Capacitor builds.

## Tests that matter
- No user ever sees the same message twice (property test on the catch endpoint).
- Own messages never appear as random catches.
- A message never returns before its `return_at`, and always returns on the first catch after it.
- Reveal does not spend a catch; empty river does not spend a catch.
- `author_id` and `return_at` never appear in any client response (snapshot test).
- Filter blocks wordlist terms, phone numbers and emails in both messages and notes.
- Concurrency: two simultaneous catches by one user can't both spend the last catch.

## Open questions (owner to decide)
- Final name.
- Daily free catch count, price of extra catches, report threshold.
- Does a returned message keep drifting for others, or leave the river?
- Optional notification when something of yours is due ("The river has something for you")? It helps inactive users get their returns but hints at the surprise.
- Cold start: minimum river size before self-returns are switched on, and how many seed messages to launch with.
- Penalty for authors of auto-hidden messages: lose credits or write cooldown.

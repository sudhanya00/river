// Client mirror of backend/app/content_filter.py, for instant feedback. The server has the final say.
import wordlist from '../../backend/app/wordlist.txt?raw'

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const TERMS = wordlist
  .split(/\r?\n/)
  .map((l) => l.trim().toLowerCase())
  .filter((l) => l && !l.startsWith('#'))
  .map((t) => new RegExp('\\b' + escape(t) + '\\b'))

export const BLOCKED_WORDS = 'That includes words the river doesn’t carry. Try rewording it.'
export const BLOCKED_PII = 'Remove phone numbers and email addresses. Messages stay anonymous.'

export function blocked(text: string): string {
  const low = text.toLowerCase()
  if (TERMS.some((t) => t.test(low))) return BLOCKED_WORDS
  if (/\d{10,}/.test(text.replace(/[\s\-().+]/g, '')) || /[^\s@]+@[^\s@]+\.[^\s@]+/.test(text)) return BLOCKED_PII
  return ''
}

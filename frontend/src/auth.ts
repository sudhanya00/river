// Supabase Auth: Google sign-in and email magic links. Supabase only issues the session; every river
// call goes to our own API with the access token as a Bearer header (see api.ts).
import { createClient, type Session } from '@supabase/supabase-js'
import { useEffect, useState } from 'react'

const url = import.meta.env.VITE_SUPABASE_URL
const key = import.meta.env.VITE_SUPABASE_ANON_KEY

export const supabase = url && key ? createClient(url, key, { auth: { flowType: 'pkce' } }) : null

export async function accessToken(): Promise<string | null> {
  if (!supabase) return null
  // getSession refreshes an expired access token using the stored refresh token.
  const { data } = await supabase.auth.getSession()
  return data.session?.access_token ?? null
}

export function useSession(): { ready: boolean; session: Session | null } {
  const [state, setState] = useState<{ ready: boolean; session: Session | null }>({ ready: !supabase, session: null })
  useEffect(() => {
    if (!supabase) return
    supabase.auth.getSession().then(({ data }) => setState({ ready: true, session: data.session }))
    const { data } = supabase.auth.onAuthStateChange((_event, session) => setState({ ready: true, session }))
    return () => data.subscription.unsubscribe()
  }, [])
  return state
}

const back = () => window.location.origin + window.location.pathname

export async function signInWithGoogle() {
  if (!supabase) throw new Error('Sign-in isn’t set up yet.')
  const { error } = await supabase.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: back() } })
  if (error) throw error
}

export async function sendMagicLink(email: string) {
  if (!supabase) throw new Error('Sign-in isn’t set up yet.')
  const { error } = await supabase.auth.signInWithOtp({ email, options: { emailRedirectTo: back() } })
  if (error) throw error
}

export async function signOut() {
  await supabase?.auth.signOut()
}

export function browserTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || ''
  } catch {
    return ''
  }
}

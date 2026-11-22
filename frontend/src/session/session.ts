import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'

import { ApiError } from '../api/apiError'
import { sessionApi, type Account, type Credentials, type NewAccount } from '../api/session'
import type { MutationMeta } from '../app/queryClient'

export const sessionKey = ['session'] as const
export const sessionEndedKey = ['session-ended'] as const

export const AUTHENTICATION_REQUIRED = 'authentication-required'

async function currentAccountOrNull(): Promise<Account | null> {
  try {
    return await sessionApi.current()
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return null
    }
    throw error
  }
}

export function useSession() {
  return useQuery({
    queryKey: sessionKey,
    queryFn: currentAccountOrNull,
    staleTime: 60_000,
    retry: false,
  })
}

export function useIsAdmin(): boolean {
  return useSession().data?.role === 'ADMIN'
}

export function startSession(client: QueryClient, account: Account | null): void {
  client.removeQueries({
    predicate: (query) => query.queryKey[0] !== sessionKey[0],
  })
  client.setQueryData(sessionKey, account)
  client.setQueryData(sessionEndedKey, false)
}

export function endSession(client: QueryClient): void {
  if (client.getQueryData(sessionKey)) {
    client.setQueryData(sessionEndedKey, true)
  }
  client.setQueryData(sessionKey, null)
}

export function isSessionEnded(error: unknown): boolean {
  return error instanceof ApiError && error.problem === AUTHENTICATION_REQUIRED
}

const loginMeta: MutationMeta = {
  handledProblems: ['invalid-credentials', 'too-many-login-attempts'],
}

export function useLogIn() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (credentials: Credentials) => sessionApi.logIn(credentials),
    onSuccess: (account) => startSession(client, account),
    meta: loginMeta,
  })
}

export function useSignUp() {
  const client = useQueryClient()
  const meta: MutationMeta = { handledProblems: ['email-already-registered'] }
  return useMutation({
    mutationFn: (account: NewAccount) => sessionApi.signUp(account),
    onSuccess: (account) => startSession(client, account),
    meta,
  })
}

export function useLogOut() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => sessionApi.logOut(),
    onSettled: () => startSession(client, null),
  })
}

export function safeNext(next: string | null): string | null {
  if (next === null || !next.startsWith('/') || next.startsWith('//') || next.includes('\\')) {
    return null
  }
  return next
}

export function landingFor(account: Account, next: string | null): string {
  const target = safeNext(next)
  const admin = account.role === 'ADMIN'
  if (target !== null && target.startsWith('/admin') === admin && !target.startsWith('/login')) {
    return target
  }
  return admin ? '/admin/products' : '/'
}

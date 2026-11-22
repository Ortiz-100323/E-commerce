import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'

import { ApiError } from '../api/apiError'
import { describeProblem, type NoticeContent } from '../notifications/describeProblem'
import { endSession, isSessionEnded } from '../session/session'

export const MAX_QUERY_RETRIES = 2

type Options = {
  notify: (notice: NoticeContent) => void
  retryDelay?: (attempt: number) => number
}

export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  return failureCount < MAX_QUERY_RETRIES && error instanceof ApiError && error.isRetryable
}

export type MutationMeta = { handledProblems?: string[] }

export function handledBy(meta: Record<string, unknown> | undefined): string[] {
  const handled = meta?.handledProblems
  return Array.isArray(handled) ? handled.filter((item) => typeof item === 'string') : []
}

export function logUnexpected(error: unknown): void {
  if (!(error instanceof ApiError)) {
    console.error('Unexpected error', error)
  }
}

export function defaultRetryDelay(attempt: number): number {
  return Math.min(1000 * 2 ** attempt, 4000)
}

export function createQueryClient({
  notify,
  retryDelay = defaultRetryDelay,
}: Options): QueryClient {
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({
      onError: (error, query) => {
        if (isSessionEnded(error)) {
          endSession(client)
          return
        }
        if (error instanceof ApiError && handledBy(query.meta).includes(error.problem)) {
          return
        }
        logUnexpected(error)
        notify(describeProblem(error))
      },
    }),
    mutationCache: new MutationCache({
      onError: (error, _variables, _result, mutation) => {
        if (isSessionEnded(error)) {
          endSession(client)
          return
        }
        if (error instanceof ApiError && error.isValidation) {
          return
        }
        if (error instanceof ApiError && handledBy(mutation.meta).includes(error.problem)) {
          return
        }
        logUnexpected(error)
        notify(describeProblem(error))
      },
    }),
    defaultOptions: {
      queries: { retry: shouldRetryQuery, retryDelay, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  })
  return client
}

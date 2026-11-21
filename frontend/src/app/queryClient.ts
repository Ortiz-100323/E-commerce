import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'

import { ApiError } from '../api/apiError'
import { describeProblem, type NoticeContent } from '../notifications/describeProblem'

export const MAX_QUERY_RETRIES = 2

type Options = {
  notify: (notice: NoticeContent) => void
  retryDelay?: (attempt: number) => number
}

export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  return failureCount < MAX_QUERY_RETRIES && error instanceof ApiError && error.isRetryable
}

export function defaultRetryDelay(attempt: number): number {
  return Math.min(1000 * 2 ** attempt, 4000)
}

export function createQueryClient({
  notify,
  retryDelay = defaultRetryDelay,
}: Options): QueryClient {
  return new QueryClient({
    queryCache: new QueryCache({
      onError: (error) => notify(describeProblem(error)),
    }),
    mutationCache: new MutationCache({
      onError: (error) => {
        if (error instanceof ApiError && error.isValidation) {
          return
        }
        notify(describeProblem(error))
      },
    }),
    defaultOptions: {
      queries: { retry: shouldRetryQuery, retryDelay, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  })
}

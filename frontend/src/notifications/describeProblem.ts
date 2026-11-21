import { ApiError } from '../api/apiError'

export type NoticeContent = {
  title: string
  detail?: string
  reference?: string
}

const UNEXPECTED = 'Something unexpected went wrong. Please try again.'

export function describeProblem(error: unknown): NoticeContent {
  if (!(error instanceof ApiError)) {
    return { title: UNEXPECTED }
  }
  const reference = error.status >= 500 || error.status === 0 ? error.requestId : undefined
  return {
    title: error.title,
    detail: error.detail,
    reference,
  }
}

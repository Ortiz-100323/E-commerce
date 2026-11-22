import { ApiError } from './apiError'

export const API_PREFIX = '/api/v1'
export const IDEMPOTENCY_HEADER = 'Idempotency-Key'

type QueryValue = string | number | boolean | null | undefined

export type RequestOptions = {
  body?: unknown
  file?: Blob
  query?: Record<string, QueryValue>
  idempotencyKey?: string
}

export const CSV_MEDIA_TYPE = 'text/csv'

export function apiUrl(path: string, query: Record<string, QueryValue> = {}): URL {
  const url = new URL(`${API_PREFIX}${path}`, window.location.origin)
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, String(value))
    }
  }
  return url
}

export async function request<T>(
  method: string,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json, application/problem+json' }
  let body: BodyInit | undefined
  if (options.file !== undefined) {
    headers['Content-Type'] = options.file.type || CSV_MEDIA_TYPE
    body = options.file
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }
  if (options.idempotencyKey !== undefined) {
    headers[IDEMPOTENCY_HEADER] = options.idempotencyKey
  }
  let response: Response
  try {
    response = await fetch(apiUrl(path, options.query), {
      method,
      headers,
      body,
      credentials: 'same-origin',
    })
  } catch {
    throw ApiError.network()
  }
  if (!response.ok) {
    throw await ApiError.fromResponse(response)
  }
  if (response.status === 204) {
    return undefined as T
  }
  try {
    return (await response.json()) as T
  } catch {
    throw ApiError.invalidResponse(response)
  }
}

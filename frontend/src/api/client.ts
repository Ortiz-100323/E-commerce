import { ApiError } from './apiError'

export const API_PREFIX = '/api/v1'
export const ACTOR_HEADER = 'X-Actor-Name'

type QueryValue = string | number | boolean | null | undefined

export type RequestOptions = {
  body?: unknown
  query?: Record<string, QueryValue>
  actor?: string
}

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
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }
  if (options.actor !== undefined) {
    headers[ACTOR_HEADER] = encodeURIComponent(options.actor)
  }
  let response: Response
  try {
    response = await fetch(apiUrl(path, options.query), {
      method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
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

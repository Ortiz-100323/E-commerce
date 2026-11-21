export const PROBLEM_PREFIX = 'urn:ecommerce:problem:'
export const NETWORK_ERROR = 'network-error'
export const INVALID_RESPONSE = 'invalid-response'

export type FieldProblem = {
  location: string
  field: string
  code: string
  message: string
  params: Record<string, unknown>
}

type ApiErrorInit = {
  status: number
  problem: string
  title: string
  detail?: string
  requestId?: string
  errors?: FieldProblem[]
  body?: Record<string, unknown>
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function text(value: unknown): string | undefined {
  return typeof value === 'string' && value !== '' ? value : undefined
}

function fieldProblems(value: unknown): FieldProblem[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter(isRecord).map((item) => ({
    location: text(item.location) ?? 'body',
    field: text(item.field) ?? '',
    code: text(item.code) ?? 'invalid',
    message: text(item.message) ?? 'This value is not valid.',
    params: isRecord(item.params) ? item.params : {},
  }))
}

export class ApiError extends Error {
  readonly status: number
  readonly problem: string
  readonly title: string
  readonly detail?: string
  readonly requestId?: string
  readonly errors: FieldProblem[]
  readonly body: Record<string, unknown>

  constructor(init: ApiErrorInit) {
    super(init.detail ?? init.title)
    this.name = 'ApiError'
    this.status = init.status
    this.problem = init.problem
    this.title = init.title
    this.detail = init.detail
    this.requestId = init.requestId
    this.errors = init.errors ?? []
    this.body = init.body ?? {}
  }

  get isValidation(): boolean {
    return this.status === 422 && this.errors.length > 0
  }

  get isServerError(): boolean {
    return this.status >= 500
  }

  get isRetryable(): boolean {
    return this.problem === NETWORK_ERROR || this.isServerError
  }

  static network(): ApiError {
    return new ApiError({
      status: 0,
      problem: NETWORK_ERROR,
      title: "We can't reach the server. Check your connection and try again.",
    })
  }

  static invalidResponse(response: Response): ApiError {
    return new ApiError({
      status: response.status,
      problem: INVALID_RESPONSE,
      title: `Something went wrong (status ${response.status}). Please try again.`,
      requestId: response.headers.get('X-Request-ID') ?? undefined,
    })
  }

  static async fromResponse(response: Response): Promise<ApiError> {
    let body: unknown
    try {
      body = await response.json()
    } catch {
      return ApiError.invalidResponse(response)
    }
    const type = isRecord(body) ? text(body.type) : undefined
    if (!isRecord(body) || type === undefined || text(body.title) === undefined) {
      return ApiError.invalidResponse(response)
    }
    return new ApiError({
      status: response.status,
      problem: type.startsWith(PROBLEM_PREFIX) ? type.slice(PROBLEM_PREFIX.length) : type,
      title: text(body.title) ?? '',
      detail: text(body.detail),
      requestId: text(body.request_id) ?? response.headers.get('X-Request-ID') ?? undefined,
      errors: fieldProblems(body.errors),
      body,
    })
  }
}

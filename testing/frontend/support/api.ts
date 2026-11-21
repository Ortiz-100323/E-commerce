import { HttpResponse } from 'msw/http'

export const API = '*/api/v1'
export const PRODUCT_ID = '40d20d85-b3d4-4ad0-a82c-4c396bfd7d6c'

export const product = {
  id: PRODUCT_ID,
  sku: 'GC-001',
  name: 'Gift Card',
  description: '',
  category: 'Gifts',
  price: '0.00',
  currency: 'USD',
  stock: 10,
  weight_kg: '0.000',
  gift: true,
  tags: ['GIFT'],
  status: 'ACTIVE',
  is_sellable: true,
  version: 1,
  created_at: '2026-11-21T16:53:59Z',
  updated_at: '2026-11-21T16:53:59Z',
}

type ProblemInit = {
  status: number
  slug: string
  title: string
  detail?: string
  requestId?: string
  extra?: Record<string, unknown>
}

export function problem({
  status,
  slug,
  title,
  detail,
  requestId = 'req-123',
  extra,
}: ProblemInit) {
  return HttpResponse.json(
    {
      type: `urn:ecommerce:problem:${slug}`,
      title,
      status,
      instance: '/api/v1/test',
      request_id: requestId,
      ...(detail ? { detail } : {}),
      ...extra,
    },
    {
      status,
      headers: { 'Content-Type': 'application/problem+json', 'X-Request-ID': requestId },
    },
  )
}

export function validationProblem(
  errors: { location?: string; field: string; code: string; message: string }[],
) {
  return problem({
    status: 422,
    slug: 'validation-error',
    title: 'The request is not valid.',
    detail: `${errors.length} fields are not valid.`,
    extra: {
      errors: errors.map((error) => ({ location: 'body', params: {}, ...error })),
    },
  })
}

export function serverError(requestId = 'req-500') {
  return problem({
    status: 500,
    slug: 'internal-error',
    title: 'An unexpected error occurred.',
    requestId,
  })
}

import { http, HttpResponse } from 'msw/http'
import { describe, expect, it } from 'vitest'

import { ApiError, NETWORK_ERROR, INVALID_RESPONSE } from '../../frontend/src/api/apiError'
import { apiUrl } from '../../frontend/src/api/client'
import { importsApi } from '../../frontend/src/api/imports'
import { productsApi } from '../../frontend/src/api/products'
import { API, PRODUCT_ID, problem, product, serverError, validationProblem } from './support/api'
import { server } from './support/server'

async function caught(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise
  } catch (error) {
    expect(error).toBeInstanceOf(ApiError)
    return error as ApiError
  }
  throw new Error('The request was expected to fail.')
}

describe('the API client', () => {
  it('returns the parsed body of a successful response', async () => {
    server.use(http.get(`${API}/products/:id`, () => HttpResponse.json(product)))

    await expect(productsApi.get(PRODUCT_ID)).resolves.toEqual(product)
  })

  it('turns a Problem Details response into an ApiError with every field', async () => {
    server.use(
      http.put(`${API}/products/:id`, () =>
        problem({
          status: 409,
          slug: 'version-conflict',
          title: 'The product was changed by someone else. Reload it and try again.',
          detail: 'You edited version 1, but the product is now at version 2.',
          requestId: 'req-409',
          extra: { current_version: 2 },
        }),
      ),
    )

    const error = await caught(productsApi.update(PRODUCT_ID, { ...product, version: 1 }, 'Maria'))

    expect(error.status).toBe(409)
    expect(error.problem).toBe('version-conflict')
    expect(error.title).toBe('The product was changed by someone else. Reload it and try again.')
    expect(error.detail).toBe('You edited version 1, but the product is now at version 2.')
    expect(error.requestId).toBe('req-409')
    expect(error.body.current_version).toBe(2)
    expect(error.isValidation).toBe(false)
    expect(error.isRetryable).toBe(false)
  })

  it('keeps the field errors of a validation problem', async () => {
    server.use(
      http.post(`${API}/products`, () =>
        validationProblem([
          { field: 'price', code: 'zero_price_requires_gift', message: 'Confirm it as a gift.' },
          { location: 'header', field: 'X-Actor-Name', code: 'required', message: 'Required.' },
        ]),
      ),
    )

    const error = await caught(productsApi.create({ ...product, sku: 'GC-001' }, 'Maria'))

    expect(error.isValidation).toBe(true)
    expect(error.errors).toEqual([
      {
        location: 'body',
        field: 'price',
        code: 'zero_price_requires_gift',
        message: 'Confirm it as a gift.',
        params: {},
      },
      {
        location: 'header',
        field: 'X-Actor-Name',
        code: 'required',
        message: 'Required.',
        params: {},
      },
    ])
  })

  it('marks server errors as retryable and keeps the request id', async () => {
    server.use(http.get(`${API}/products/:id`, () => serverError('req-boom')))

    const error = await caught(productsApi.get(PRODUCT_ID))

    expect(error.status).toBe(500)
    expect(error.isServerError).toBe(true)
    expect(error.isRetryable).toBe(true)
    expect(error.requestId).toBe('req-boom')
  })

  it('turns a network failure into a retryable network error', async () => {
    server.use(http.get(`${API}/products/:id`, () => HttpResponse.error()))

    const error = await caught(productsApi.get(PRODUCT_ID))

    expect(error.problem).toBe(NETWORK_ERROR)
    expect(error.status).toBe(0)
    expect(error.isRetryable).toBe(true)
    expect(error.title).toBe("We can't reach the server. Check your connection and try again.")
  })

  it('handles an HTML error page from the proxy without crashing', async () => {
    server.use(
      http.get(
        `${API}/products/:id`,
        () =>
          new HttpResponse('<html><body>502 Bad Gateway</body></html>', {
            status: 502,
            headers: { 'Content-Type': 'text/html', 'X-Request-ID': 'req-proxy' },
          }),
      ),
    )

    const error = await caught(productsApi.get(PRODUCT_ID))

    expect(error.problem).toBe(INVALID_RESPONSE)
    expect(error.status).toBe(502)
    expect(error.title).toBe('Something went wrong (status 502). Please try again.')
    expect(error.requestId).toBe('req-proxy')
    expect(error.isRetryable).toBe(true)
  })

  it('handles JSON that is not Problem Details', async () => {
    server.use(
      http.get(`${API}/products/:id`, () =>
        HttpResponse.json({ message: 'nope' }, { status: 418 }),
      ),
    )

    const error = await caught(productsApi.get(PRODUCT_ID))

    expect(error.problem).toBe(INVALID_RESPONSE)
    expect(error.status).toBe(418)
  })

  it('handles a successful response whose body is not JSON', async () => {
    server.use(
      http.get(
        `${API}/products/:id`,
        () =>
          new HttpResponse('not json', { status: 200, headers: { 'Content-Type': 'text/plain' } }),
      ),
    )

    const error = await caught(productsApi.get(PRODUCT_ID))

    expect(error.problem).toBe(INVALID_RESPONSE)
    expect(error.status).toBe(200)
  })

  it('sends the reviewer name percent-encoded on every change', async () => {
    const seen: (string | null)[] = []
    const record = ({ request }: { request: Request }) => {
      seen.push(request.headers.get('X-Actor-Name'))
      return HttpResponse.json(product)
    }
    server.use(
      http.post(`${API}/products`, record),
      http.put(`${API}/products/:id`, record),
      http.delete(`${API}/products/:id`, record),
      http.post(`${API}/products/:id/restore`, record),
    )

    await productsApi.create({ ...product, sku: 'GC-001' }, 'Łukasz')
    await productsApi.update(PRODUCT_ID, { ...product, version: 1 }, 'Maria Silva')
    await productsApi.archive(PRODUCT_ID, '李')
    await productsApi.restore(PRODUCT_ID, 'Antonio')

    expect(seen).toEqual(['%C5%81ukasz', 'Maria%20Silva', '%E6%9D%8E', 'Antonio'])
  })

  it('sends no reviewer name on reads', async () => {
    let header: string | null = 'unset'
    server.use(
      http.get(`${API}/products`, ({ request }) => {
        header = request.headers.get('X-Actor-Name')
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20 })
      }),
    )

    await productsApi.search()

    expect(header).toBeNull()
  })

  it('keeps the selected file media type so the server can reject a non-CSV upload', async () => {
    let contentType: string | null = null
    server.use(
      http.post(`${API}/imports`, ({ request }) => {
        contentType = request.headers.get('Content-Type')
        return HttpResponse.json({ id: 'import-1' })
      }),
    )

    await importsApi.upload(
      new File(['not a csv'], 'products.txt', { type: 'text/plain' }),
      'Maria',
    )

    expect(contentType).toBe('text/plain')
  })

  it('builds search URLs without empty parameters', () => {
    const url = apiUrl('/products', {
      q: '100%',
      category: '',
      in_stock: false,
      page: 2,
      tag: undefined,
    })

    expect(url.pathname).toBe('/api/v1/products')
    expect(url.searchParams.get('q')).toBe('100%')
    expect(url.searchParams.has('category')).toBe(false)
    expect(url.searchParams.has('tag')).toBe(false)
    expect(url.searchParams.get('in_stock')).toBe('false')
    expect(url.searchParams.get('page')).toBe('2')
  })

  it('calls every product endpoint with the right method and path', async () => {
    const calls: string[] = []
    const record =
      (body: unknown) =>
      ({ request }: { request: Request }) => {
        const url = new URL(request.url)
        calls.push(`${request.method} ${url.pathname}${url.search}`)
        return HttpResponse.json(body)
      }
    server.use(
      http.get(`${API}/products`, record({ items: [], total: 0, page: 1, page_size: 20 })),
      http.get(`${API}/products/:id/history`, record({ product_id: PRODUCT_ID, entries: [] })),
      http.get(`${API}/products/:id`, record(product)),
      http.get(`${API}/categories`, record({ items: ['Gifts'] })),
    )

    await productsApi.search({ q: 'shoes', status: 'ALL', sort: '-price' })
    await productsApi.get(PRODUCT_ID)
    await productsApi.history(PRODUCT_ID)
    await expect(productsApi.categories()).resolves.toEqual({ items: ['Gifts'] })

    expect(calls).toEqual([
      'GET /api/v1/products?q=shoes&status=ALL&sort=-price',
      `GET /api/v1/products/${PRODUCT_ID}`,
      `GET /api/v1/products/${PRODUCT_ID}/history`,
      'GET /api/v1/categories',
    ])
  })
})

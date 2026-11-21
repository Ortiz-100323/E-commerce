import { useMutation, useQuery } from '@tanstack/react-query'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw/http'
import { describe, expect, it } from 'vitest'

import { ApiError } from '../../frontend/src/api/apiError'
import { productsApi } from '../../frontend/src/api/products'
import { AppShell } from '../../frontend/src/app/AppShell'
import { describeProblem } from '../../frontend/src/notifications/describeProblem'
import { API, PRODUCT_ID, problem, product, serverError } from './support/api'
import { renderApp } from './support/renderApp'
import { server } from './support/server'

function ProductProbe() {
  const query = useQuery({
    queryKey: ['product', PRODUCT_ID],
    queryFn: () => productsApi.get(PRODUCT_ID),
  })
  const archive = useMutation({ mutationFn: () => productsApi.archive(PRODUCT_ID, 'Maria') })
  return (
    <div>
      <p>{query.isError ? 'Could not load' : query.data ? query.data.name : 'Loading'}</p>
      <button type="button" onClick={() => archive.mutate()}>
        Archive
      </button>
    </div>
  )
}

const probeRoutes = [
  { element: <AppShell />, children: [{ path: 'probe', element: <ProductProbe /> }] },
]

function notifications() {
  return within(screen.getByRole('region', { name: 'Notifications' }))
}

function countRequests(method: 'get' | 'delete', respond: () => Response) {
  const counter = { count: 0 }
  const handler = method === 'get' ? http.get : http.delete
  server.use(
    handler(`${API}/products/:id`, () => {
      counter.count += 1
      return respond()
    }),
  )
  return counter
}

describe('notifications for problems', () => {
  it('shows a 5xx problem with its request id after retrying the read twice', async () => {
    const reads = countRequests('get', () => serverError('req-7f3a'))
    renderApp('/probe', { routes: probeRoutes })

    const notice = await notifications().findByRole('alert')
    expect(within(notice).getByText('An unexpected error occurred.')).toBeInTheDocument()
    expect(within(notice).getByText('Reference: req-7f3a')).toBeInTheDocument()
    expect(screen.getByText('Could not load')).toBeInTheDocument()
    expect(reads.count).toBe(3)
  })

  it('recovers silently when a retried read succeeds', async () => {
    let attempts = 0
    server.use(
      http.get(`${API}/products/:id`, () => {
        attempts += 1
        return attempts === 1 ? serverError() : HttpResponse.json(product)
      }),
    )
    renderApp('/probe', { routes: probeRoutes })

    expect(await screen.findByText('Gift Card')).toBeInTheDocument()
    expect(notifications().queryByRole('alert')).not.toBeInTheDocument()
    expect(attempts).toBe(2)
  })

  it('does not retry a 404 and shows its title and detail without a reference', async () => {
    const reads = countRequests('get', () =>
      problem({
        status: 404,
        slug: 'not-found',
        title: 'The resource was not found.',
        detail: 'Product not found.',
      }),
    )
    renderApp('/probe', { routes: probeRoutes })

    const notice = await notifications().findByRole('alert')
    expect(within(notice).getByText('The resource was not found.')).toBeInTheDocument()
    expect(within(notice).getByText('Product not found.')).toBeInTheDocument()
    expect(within(notice).queryByText(/Reference/)).not.toBeInTheDocument()
    expect(reads.count).toBe(1)
  })

  it('tells the person when the server cannot be reached', async () => {
    const reads = countRequests('get', () => HttpResponse.error())
    renderApp('/probe', { routes: probeRoutes })

    const notice = await notifications().findByRole('alert')
    expect(
      within(notice).getByText("We can't reach the server. Check your connection and try again."),
    ).toBeInTheDocument()
    expect(reads.count).toBe(3)
  })

  it('never retries a failed change and shows the 5xx reference', async () => {
    countRequests('get', () => HttpResponse.json(product))
    const changes = countRequests('delete', () => serverError('req-del'))
    renderApp('/probe', { routes: probeRoutes })
    await screen.findByText('Gift Card')

    await userEvent.click(screen.getByRole('button', { name: 'Archive' }))

    const notice = await notifications().findByRole('alert')
    expect(within(notice).getByText('Reference: req-del')).toBeInTheDocument()
    expect(changes.count).toBe(1)
  })

  it('shows a conflict from a change with its title', async () => {
    countRequests('get', () => HttpResponse.json(product))
    const changes = countRequests('delete', () =>
      problem({
        status: 409,
        slug: 'version-conflict',
        title: 'The product was changed by someone else. Reload it and try again.',
      }),
    )
    renderApp('/probe', { routes: probeRoutes })
    await screen.findByText('Gift Card')

    await userEvent.click(screen.getByRole('button', { name: 'Archive' }))

    expect(
      await notifications().findByText(
        'The product was changed by someone else. Reload it and try again.',
      ),
    ).toBeInTheDocument()
    expect(changes.count).toBe(1)
  })

  it('can dismiss a notification', async () => {
    countRequests('get', () => serverError())
    renderApp('/probe', { routes: probeRoutes })
    const notice = await notifications().findByRole('alert')

    await userEvent.click(within(notice).getByRole('button', { name: 'Dismiss' }))

    expect(notifications().queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('describeProblem', () => {
  it('describes an unknown error with a generic message', () => {
    expect(describeProblem(new Error('boom'))).toEqual({
      title: 'Something unexpected went wrong. Please try again.',
    })
  })

  it('adds the reference only for server errors', () => {
    const conflict = new ApiError({
      status: 409,
      problem: 'duplicate-sku',
      title: 'Taken.',
      requestId: 'r1',
    })
    const failure = new ApiError({
      status: 503,
      problem: 'service-unavailable',
      title: 'Down.',
      requestId: 'r2',
    })

    expect(describeProblem(conflict).reference).toBeUndefined()
    expect(describeProblem(failure).reference).toBe('r2')
  })
})

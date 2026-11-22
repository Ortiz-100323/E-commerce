import { http, HttpResponse } from 'msw/http'

import type { AdminOrder, OrderStatus } from '../../../frontend/src/api/orders'
import { API, problem } from './api'
import { requireAdmin } from './fakeSession'
import { server } from './server'

const PAGE_SIZE = 20

export function adminOrder(
  number: number,
  overrides: Partial<AdminOrder> & { name?: string; email?: string } = {},
): AdminOrder {
  const { name = 'Ana Souza', email = 'ana@example.com', ...rest } = overrides
  const id = `${String(number).padStart(8, '0')}-0000-4000-8000-000000000000`
  return {
    id,
    status: 'PAID',
    customer: { name, email },
    lines: [
      {
        sku: 'RS-001',
        product_id: 'p-1',
        name: 'Running Shoes',
        unit_price: '89.99',
        quantity: 2,
        gift: false,
        line_total: '179.98',
      },
    ],
    total: '179.98',
    currency: 'USD',
    card_last4: '4242',
    payment_reference: `fake_${number}`,
    decline_reason: null,
    created_at: `2026-11-${String(10 + (number % 18)).padStart(2, '0')}T10:00:00Z`,
    settled_at: null,
    customer_account: false,
    ...rest,
  }
}

export function fakeAdminOrders(orders: AdminOrder[]) {
  const queries: Record<string, string>[] = []
  server.use(
    http.get(`${API}/admin/orders`, ({ request }) => {
      const refused = requireAdmin()
      if (refused) {
        return refused
      }
      const params = new URL(request.url).searchParams
      queries.push(Object.fromEntries(params))
      const q = (params.get('q') ?? '').toLowerCase()
      const status = params.get('status') as OrderStatus | null
      const page = Number(params.get('page') ?? '1')
      const found = orders.filter(
        (order) =>
          (status === null || order.status === status) &&
          (!q ||
            order.customer.name.toLowerCase().includes(q) ||
            order.customer.email.toLowerCase().includes(q) ||
            order.id.startsWith(q)),
      )
      return HttpResponse.json({
        items: found.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
        total: found.length,
        page,
        page_size: PAGE_SIZE,
      })
    }),
    http.get(`${API}/admin/orders/:id`, ({ params }) => {
      const refused = requireAdmin()
      if (refused) {
        return refused
      }
      const order = orders.find((item) => item.id === params.id)
      return order
        ? HttpResponse.json(order)
        : problem({ status: 404, slug: 'not-found', title: 'The resource was not found.' })
    }),
  )
  return { queries }
}

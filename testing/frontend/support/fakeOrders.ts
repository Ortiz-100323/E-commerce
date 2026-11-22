import { http, HttpResponse } from 'msw/http'

import type { Order, Quote, QuoteLine } from '../../../frontend/src/api/orders'
import { API, problem, validationProblem } from './api'
import { server } from './server'

export type ShopItem = {
  sku: string
  name: string
  price: string
  stock: number
  active?: boolean
}

type CheckoutBody = {
  customer: { name: string; email: string }
  lines: { sku: string; quantity: number }[]
  payment?: { card_number: string; expiry_month: number; expiry_year: number; cvc: string }
}

type Placed = { key: string | null; body: CheckoutBody }

export const DECLINED_CARD = '4000000000000002'
const ORDER_PREFIX = '00000000-0000-4000-9000-'

function money(value: number): string {
  return value.toFixed(2)
}

function digits(card: string): string {
  return card.replace(/[\s-]/g, '')
}

export function fakeOrders(items: ShopItem[]) {
  const shop = new Map(items.map((item) => [item.sku, { active: true, ...item }]))
  const orders = new Map<string, Order>()
  const keys = new Map<string, { fingerprint: string; orderId: string; status: number }>()
  const placed: Placed[] = []
  const quotes: { sku: string; quantity: number }[][] = []
  const failures: Response[] = []
  let counter = 0

  function merged(lines: { sku: string; quantity: number }[]) {
    const totals = new Map<string, number>()
    for (const line of lines) {
      const sku = line.sku.trim().toUpperCase()
      totals.set(sku, (totals.get(sku) ?? 0) + line.quantity)
    }
    return [...totals.entries()].sort(([a], [b]) => a.localeCompare(b))
  }

  function quoteOf(lines: { sku: string; quantity: number }[]): Quote {
    const quoted: QuoteLine[] = merged(lines).map(([sku, quantity]) => {
      const item = shop.get(sku)
      if (item === undefined) {
        return {
          sku,
          product_id: null,
          name: null,
          unit_price: null,
          quantity,
          gift: false,
          available: 0,
          line_total: null,
          problem: 'unknown',
        }
      }
      const available = item.active ? item.stock : 0
      const problemOf = !item.active
        ? 'archived'
        : item.stock === 0
          ? 'out_of_stock'
          : quantity > item.stock
            ? 'insufficient_stock'
            : null
      return {
        sku,
        product_id: `product-${sku}`,
        name: item.name,
        unit_price: item.price,
        quantity,
        gift: Number(item.price) === 0,
        available,
        line_total: money(Number(item.price) * quantity),
        problem: problemOf,
      }
    })
    const total = quoted
      .filter((line) => line.problem === null)
      .reduce((sum, line) => sum + Number(line.line_total), 0)
    return {
      lines: quoted,
      total: money(total),
      currency: 'USD',
      ready: quoted.every((line) => line.problem === null),
      payment_required: total > 0,
    }
  }

  function answer(order: Order, replayed: boolean) {
    const headers: Record<string, string> = replayed ? { 'Idempotent-Replayed': 'true' } : {}
    if (order.status === 'PAYMENT_FAILED') {
      return problem({
        status: 402,
        slug: 'payment-declined',
        title: 'The card was declined.',
        detail: 'Nothing was charged and no stock was taken. Try another card.',
        extra: { order_id: order.id, order },
      })
    }
    return HttpResponse.json(order, { status: 201, headers })
  }

  function checkout(body: CheckoutBody, key: string): Response {
    const quote = quoteOf(body.lines)
    const unsellable = quote.lines.filter(
      (line) => line.problem !== null && line.problem !== 'insufficient_stock',
    )
    if (unsellable.length > 0) {
      return problem({
        status: 409,
        slug: 'product-not-sellable',
        title: "Some products in the cart can't be bought right now.",
        extra: { items: unsellable.map((line) => ({ sku: line.sku, reason: line.problem })) },
      })
    }
    const short = quote.lines.filter((line) => line.problem === 'insufficient_stock')
    if (short.length > 0) {
      return problem({
        status: 409,
        slug: 'insufficient-stock',
        title: 'Some items are no longer available in the requested quantity.',
        extra: {
          items: short.map((line) => ({
            sku: line.sku,
            requested: line.quantity,
            available: line.available,
          })),
        },
      })
    }
    if (quote.payment_required && body.payment === undefined) {
      return validationProblem([
        { field: 'payment', code: 'required', message: 'Enter a card to pay.' },
      ])
    }
    counter += 1
    const card = body.payment === undefined ? null : digits(body.payment.card_number)
    const declined = card === DECLINED_CARD
    const order: Order = {
      id: `${ORDER_PREFIX}${String(counter).padStart(12, '0')}`,
      status: declined ? 'PAYMENT_FAILED' : 'PAID',
      customer: {
        name: body.customer.name.trim(),
        email: body.customer.email.trim().toLowerCase(),
      },
      lines: quote.lines.map((line) => ({
        sku: line.sku,
        product_id: line.product_id ?? '',
        name: line.name ?? '',
        unit_price: line.unit_price ?? '0.00',
        quantity: line.quantity,
        gift: line.gift,
        line_total: line.line_total ?? '0.00',
      })),
      total: quote.total,
      currency: 'USD',
      card_last4: quote.payment_required && card !== null ? card.slice(-4) : null,
      payment_reference: declined || !quote.payment_required ? null : `fake_${counter}`,
      decline_reason: declined ? 'card_declined' : null,
      created_at: '2026-11-22T10:00:00Z',
      settled_at: '2026-11-22T10:00:00Z',
    }
    if (!declined) {
      for (const line of quote.lines) {
        const item = shop.get(line.sku)
        if (item !== undefined) {
          item.stock -= line.quantity
        }
      }
    }
    orders.set(order.id, order)
    keys.set(key, {
      fingerprint: JSON.stringify({ ...body, payment: card?.slice(-4) ?? null }),
      orderId: order.id,
      status: declined ? 402 : 201,
    })
    return answer(order, false)
  }

  server.use(
    http.post(`${API}/orders/quote`, async ({ request }) => {
      const body = (await request.json()) as { lines: { sku: string; quantity: number }[] }
      quotes.push(body.lines)
      return HttpResponse.json(quoteOf(body.lines))
    }),
    http.post(`${API}/orders`, async ({ request }) => {
      const key = request.headers.get('Idempotency-Key')
      const body = (await request.json()) as CheckoutBody
      placed.push({ key, body })
      const failure = failures.shift()
      if (failure !== undefined) {
        return failure
      }
      if (!key) {
        return problem({
          status: 400,
          slug: 'idempotency-key-missing',
          title: 'The Idempotency-Key header is required.',
        })
      }
      const seen = keys.get(key)
      if (seen !== undefined) {
        const fingerprint = JSON.stringify({
          ...body,
          payment: body.payment ? digits(body.payment.card_number).slice(-4) : null,
        })
        if (fingerprint !== seen.fingerprint) {
          return problem({
            status: 422,
            slug: 'idempotency-key-reused',
            title: 'This Idempotency-Key was already used for a different request.',
          })
        }
        const order = orders.get(seen.orderId)
        return answer(order as Order, true)
      }
      return checkout(body, key)
    }),
    http.get(`${API}/orders/:orderId`, ({ params }) => {
      const order = orders.get(String(params.orderId))
      if (order === undefined) {
        return problem({ status: 404, slug: 'not-found', title: 'The resource was not found.' })
      }
      return HttpResponse.json(order)
    }),
  )

  return {
    shop,
    orders,
    placed,
    quotes,
    failNext: (response: Response) => failures.push(response),
    setStock: (sku: string, stock: number) => {
      const item = shop.get(sku)
      if (item !== undefined) {
        item.stock = stock
      }
    },
  }
}

import { request } from './client'

export type LineProblem = 'unknown' | 'archived' | 'out_of_stock' | 'insufficient_stock'

export type QuoteLine = {
  sku: string
  product_id: string | null
  name: string | null
  unit_price: string | null
  quantity: number
  gift: boolean
  available: number
  line_total: string | null
  problem: LineProblem | null
}

export type Quote = {
  lines: QuoteLine[]
  total: string
  currency: string
  ready: boolean
  payment_required: boolean
}

export type RequestedLine = { sku: string; quantity: number }

export type OrderLine = {
  sku: string
  product_id: string
  name: string
  unit_price: string
  quantity: number
  gift: boolean
  line_total: string
}

export type OrderStatus = 'PENDING' | 'PAID' | 'PAYMENT_FAILED'

export type Order = {
  id: string
  status: OrderStatus
  customer: { name: string; email: string }
  lines: OrderLine[]
  total: string
  currency: string
  card_last4: string | null
  payment_reference: string | null
  decline_reason: string | null
  created_at: string
  settled_at: string | null
}

export type Payment = {
  card_number: string
  expiry_month: number
  expiry_year: number
  cvc: string
}

export type CheckoutBody = {
  customer: { name: string; email: string }
  lines: RequestedLine[]
  payment?: Payment
}

export type UnsellableItem = { sku: string; reason: LineProblem }
export type ShortItem = { sku: string; requested: number; available: number }

export const ordersApi = {
  quote: (lines: RequestedLine[]) => request<Quote>('POST', '/orders/quote', { body: { lines } }),
  place: (body: CheckoutBody, idempotencyKey: string) =>
    request<Order>('POST', '/orders', { body, idempotencyKey }),
  get: (id: string) => request<Order>('GET', `/orders/${encodeURIComponent(id)}`),
}

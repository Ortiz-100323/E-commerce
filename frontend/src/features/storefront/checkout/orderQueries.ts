import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'

import { ordersApi, type CheckoutBody, type RequestedLine } from '../../../api/orders'
import type { MutationMeta } from '../../../app/queryClient'
import type { CartLine } from '../../../cart/cart'

export const orderKeys = {
  quote: (lines: RequestedLine[]) => ['orders', 'quote', lines] as const,
  detail: (id: string) => ['orders', 'detail', id] as const,
}

export const CHECKOUT_PROBLEMS = [
  'payment-declined',
  'insufficient-stock',
  'product-not-sellable',
  'validation-error',
  'idempotency-key-reused',
  'service-unavailable',
  'internal-error',
  'network-error',
  'invalid-response',
]

export function requestedLines(lines: CartLine[]): RequestedLine[] {
  return lines.map((line) => ({ sku: line.sku, quantity: line.quantity }))
}

export function useQuote(lines: CartLine[]) {
  const requested = requestedLines(lines)
  return useQuery({
    queryKey: orderKeys.quote(requested),
    queryFn: () => ordersApi.quote(requested),
    enabled: requested.length > 0,
    placeholderData: keepPreviousData,
  })
}

export function useOrder(id: string) {
  return useQuery({
    queryKey: orderKeys.detail(id),
    queryFn: () => ordersApi.get(id),
    meta: { handledProblems: ['not-found'] },
  })
}

export function usePlaceOrder() {
  const meta: MutationMeta = { handledProblems: CHECKOUT_PROBLEMS }
  return useMutation({
    mutationFn: ({ body, key }: { body: CheckoutBody; key: string }) => ordersApi.place(body, key),
    meta,
  })
}

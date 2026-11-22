import type { Product } from '../api/products'

export const CART_STORAGE_KEY = 'ecommerce.cart'

export type CartLine = {
  productId: string
  sku: string
  name: string
  price: string
  quantity: number
}

export type AddResult = 'added' | 'out_of_stock' | 'at_stock_limit'

let memory: CartLine[] = []

function isCartLine(value: unknown): value is CartLine {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const line = value as Record<string, unknown>
  return (
    typeof line.productId === 'string' &&
    typeof line.sku === 'string' &&
    typeof line.name === 'string' &&
    typeof line.price === 'string' &&
    Number.isInteger(line.quantity) &&
    (line.quantity as number) > 0
  )
}

export function readCart(): CartLine[] {
  try {
    const stored = window.localStorage.getItem(CART_STORAGE_KEY)
    if (stored === null) {
      return memory
    }
    const parsed: unknown = JSON.parse(stored)
    return Array.isArray(parsed) ? parsed.filter(isCartLine) : []
  } catch {
    return memory
  }
}

export function writeCart(lines: CartLine[]): void {
  memory = lines
  try {
    window.localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(lines))
  } catch {
    return
  }
}

export function forgetCartInMemory(): void {
  memory = []
}

export function quantityIn(lines: CartLine[], productId: string): number {
  return lines.find((line) => line.productId === productId)?.quantity ?? 0
}

export function canAdd(lines: CartLine[], product: Product): AddResult {
  if (!product.is_sellable || product.stock <= 0) {
    return 'out_of_stock'
  }
  if (quantityIn(lines, product.id) >= product.stock) {
    return 'at_stock_limit'
  }
  return 'added'
}

export function addOne(lines: CartLine[], product: Product): CartLine[] {
  const existing = lines.find((line) => line.productId === product.id)
  if (existing) {
    return lines.map((line) =>
      line.productId === product.id ? { ...line, quantity: line.quantity + 1 } : line,
    )
  }
  return [
    ...lines,
    {
      productId: product.id,
      sku: product.sku,
      name: product.name,
      price: product.price,
      quantity: 1,
    },
  ]
}

export function withQuantity(lines: CartLine[], sku: string, quantity: number): CartLine[] {
  if (quantity < 1) {
    return withoutLine(lines, sku)
  }
  return lines.map((line) => (line.sku === sku ? { ...line, quantity } : line))
}

export function withoutLine(lines: CartLine[], sku: string): CartLine[] {
  return lines.filter((line) => line.sku !== sku)
}

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'

import type { Product } from '../api/products'
import {
  addOne,
  canAdd,
  quantityIn,
  readCart,
  withoutLine,
  withQuantity,
  writeCart,
  type AddResult,
  type CartLine,
} from './cart'

type CartApi = {
  lines: CartLine[]
  count: number
  quantityOf: (productId: string) => number
  add: (product: Product) => AddResult
  setQuantity: (sku: string, quantity: number) => void
  remove: (sku: string) => void
  update: (change: (lines: CartLine[]) => CartLine[]) => void
  clear: () => void
}

const CartContext = createContext<CartApi | null>(null)

export function CartProvider({ children }: { children: ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>(() => readCart())
  const latest = useRef(lines)

  const update = useCallback((change: (current: CartLine[]) => CartLine[]) => {
    const next = change(latest.current)
    latest.current = next
    writeCart(next)
    setLines(next)
  }, [])

  const add = useCallback(
    (product: Product): AddResult => {
      const result = canAdd(latest.current, product)
      if (result === 'added') {
        update((current) => addOne(current, product))
      }
      return result
    },
    [update],
  )

  const api = useMemo(
    () => ({
      lines,
      count: lines.reduce((total, line) => total + line.quantity, 0),
      quantityOf: (productId: string) => quantityIn(lines, productId),
      add,
      setQuantity: (sku: string, quantity: number) =>
        update((current) => withQuantity(current, sku, quantity)),
      remove: (sku: string) => update((current) => withoutLine(current, sku)),
      update,
      clear: () => update(() => []),
    }),
    [lines, add, update],
  )

  return <CartContext.Provider value={api}>{children}</CartContext.Provider>
}

export function useCart(): CartApi {
  const api = useContext(CartContext)
  if (api === null) {
    throw new Error('useCart must be used inside CartProvider.')
  }
  return api
}

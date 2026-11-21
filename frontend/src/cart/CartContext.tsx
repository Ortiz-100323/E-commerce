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
  writeCart,
  type AddResult,
  type CartLine,
} from './cart'

type CartApi = {
  lines: CartLine[]
  count: number
  quantityOf: (productId: string) => number
  add: (product: Product) => AddResult
}

const CartContext = createContext<CartApi | null>(null)

export function CartProvider({ children }: { children: ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>(() => readCart())
  const latest = useRef(lines)

  const add = useCallback((product: Product): AddResult => {
    const result = canAdd(latest.current, product)
    if (result === 'added') {
      const next = addOne(latest.current, product)
      latest.current = next
      writeCart(next)
      setLines(next)
    }
    return result
  }, [])

  const api = useMemo(
    () => ({
      lines,
      count: lines.reduce((total, line) => total + line.quantity, 0),
      quantityOf: (productId: string) => quantityIn(lines, productId),
      add,
    }),
    [lines, add],
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

import { useState } from 'react'
import { Link, useNavigate } from 'react-router'

import type { QuoteLine } from '../../../api/orders'
import { useCart } from '../../../cart/CartContext'
import type { CartLine } from '../../../cart/cart'
import { formatPrice } from '../../admin/products/format'
import styles from './Checkout.module.css'
import { useQuote } from './orderQueries'

const MAX_QUANTITY = 10_000

function problemText(line: QuoteLine): string | null {
  switch (line.problem) {
    case 'insufficient_stock':
      return `Only ${line.available} left.`
    case 'out_of_stock':
      return 'Out of stock.'
    case 'archived':
      return 'No longer sold.'
    case 'unknown':
      return 'No longer in the shop.'
    default:
      return null
  }
}

function QuantityField({
  line,
  name,
  available,
}: {
  line: CartLine
  name: string
  available: number | undefined
}) {
  const cart = useCart()
  const [draft, setDraft] = useState({ quantity: line.quantity, text: String(line.quantity) })
  const text = draft.quantity === line.quantity ? draft.text : String(line.quantity)
  const ceiling = Math.min(MAX_QUANTITY, available ?? MAX_QUANTITY)

  const change = (value: string) => {
    const quantity = Number(value)
    const valid = /^\d+$/.test(value) && quantity >= 1 && quantity <= MAX_QUANTITY
    setDraft({ quantity: valid ? quantity : line.quantity, text: value })
    if (valid && quantity !== line.quantity) {
      cart.setQuantity(line.sku, quantity)
    }
  }

  const step = (by: number) => change(String(line.quantity + by))

  return (
    <div className={styles.stepper}>
      <button
        type="button"
        className={styles.step}
        aria-label={`One fewer ${name}`}
        disabled={line.quantity <= 1}
        onClick={() => step(-1)}
      >
        −
      </button>
      <input
        type="number"
        min={1}
        max={MAX_QUANTITY}
        required
        inputMode="numeric"
        className={styles.quantity}
        aria-label={`Quantity of ${name}`}
        value={text}
        onChange={(event) => change(event.target.value)}
      />
      <button
        type="button"
        className={styles.step}
        aria-label={`One more ${name}`}
        disabled={line.quantity >= ceiling}
        onClick={() => step(1)}
      >
        +
      </button>
    </div>
  )
}

function CartRow({ line, quoted }: { line: CartLine; quoted: QuoteLine | undefined }) {
  const cart = useCart()
  const name = quoted?.name ?? line.name
  const problem = quoted === undefined ? null : problemText(quoted)
  return (
    <li
      aria-label={name}
      className={styles.row}
      data-flagged={problem !== null ? 'true' : undefined}
    >
      <div className={styles.rowMain}>
        <Link to={`/products/${line.productId}`} className={styles.rowName}>
          {name}
        </Link>
        <span className={styles.muted}>
          {quoted?.unit_price ? formatPrice(quoted.unit_price, 'USD') : '…'}
        </span>
      </div>
      <QuantityField line={line} name={name} available={quoted?.available} />
      <span className={styles.amount}>
        {quoted?.line_total ? formatPrice(quoted.line_total, 'USD') : '—'}
      </span>
      <button
        type="button"
        className={styles.link}
        aria-label={`Remove ${name}`}
        onClick={() => cart.remove(line.sku)}
      >
        Remove
      </button>
      {problem !== null && quoted !== undefined ? (
        <p className={styles.problem}>
          {problem}{' '}
          {quoted.problem === 'insufficient_stock' ? (
            <button
              type="button"
              className={styles.secondary}
              onClick={() => cart.setQuantity(line.sku, quoted.available)}
            >
              Use {quoted.available}
            </button>
          ) : null}
        </p>
      ) : null}
    </li>
  )
}

export function CartPage() {
  const cart = useCart()
  const navigate = useNavigate()
  const quote = useQuote(cart.lines)

  if (cart.lines.length === 0) {
    return (
      <section aria-labelledby="cart-title" className={styles.page}>
        <h2 id="cart-title">Your cart</h2>
        <div className={styles.empty}>
          <p className={styles.emptyTitle}>Your cart is empty.</p>
          <p className={styles.muted}>Add something from the shop and it will wait for you here.</p>
          <Link to="/" className={styles.primaryLink}>
            Continue shopping
          </Link>
        </div>
      </section>
    )
  }

  const quoted = new Map((quote.data?.lines ?? []).map((line) => [line.sku, line]))
  const current = quote.data !== undefined && !quote.isPlaceholderData
  const ready = current && quote.data.ready

  return (
    <form
      aria-labelledby="cart-title"
      className={styles.page}
      onSubmit={(event) => {
        event.preventDefault()
        void navigate('/checkout')
      }}
    >
      <h2 id="cart-title">Your cart</h2>
      {quote.isError ? (
        <p role="alert" className={styles.alert}>
          The prices could not be loaded. Try again in a moment.
        </p>
      ) : null}
      <ul aria-label="Cart" className={styles.rows}>
        {cart.lines.map((line) => (
          <CartRow key={line.sku} line={line} quoted={quoted.get(line.sku.toUpperCase())} />
        ))}
      </ul>
      <div className={styles.totals}>
        {quote.data ? (
          <p
            className={styles.total}
          >{`${quote.data.ready ? 'Subtotal' : 'Subtotal of available items'}: ${formatPrice(quote.data.total, quote.data.currency)}`}</p>
        ) : (
          <p>Checking prices…</p>
        )}
        {current && !quote.data.ready ? (
          <p className={styles.hint}>Fix the items marked above before checking out.</p>
        ) : null}
        <button type="submit" className={styles.primary} disabled={!ready}>
          Go to checkout
        </button>
      </div>
    </form>
  )
}

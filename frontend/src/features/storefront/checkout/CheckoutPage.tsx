import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { useForm, type FieldPath } from 'react-hook-form'
import { Link, useNavigate } from 'react-router'

import { ApiError, type FieldProblem } from '../../../api/apiError'
import { newIdempotencyKey } from '../../../api/idempotencyKey'
import type { Quote, ShortItem, UnsellableItem } from '../../../api/orders'
import { useCart } from '../../../cart/CartContext'
import { withoutLine, withQuantity, type CartLine } from '../../../cart/cart'
import { FormProblems } from '../../../forms/FormProblems'
import formStyles from '../../../forms/Forms.module.css'
import { TextField } from '../../../forms/TextField'
import { formatPrice } from '../../admin/products/format'
import styles from './Checkout.module.css'
import {
  CHECKOUT_FIELDS,
  checkoutBody,
  emptyCheckout,
  freeCheckoutSchema,
  paidCheckoutSchema,
  SERVER_FIELD_ALIASES,
  type CheckoutValues,
} from './checkoutSchema'
import { orderKeys, requestedLines, usePlaceOrder, useQuote } from './orderQueries'

type Outcome =
  | { kind: 'declined' }
  | { kind: 'short'; items: ShortItem[] }
  | { kind: 'unsellable'; items: UnsellableItem[] }
  | { kind: 'unreachable' }
  | { kind: 'busy' }
  | { kind: 'other'; message: string }

type Attempt = { key: string; request: string }

const REASONS: Record<string, string> = {
  out_of_stock: 'is out of stock',
  archived: 'is no longer sold',
  unknown: 'is no longer in the shop',
  insufficient_stock: 'is not available in that quantity',
}

function itemsOf<T>(error: ApiError): T[] {
  const items = error.body.items
  return Array.isArray(items) ? (items as T[]) : []
}

function outcomeOf(error: unknown): Outcome {
  if (!(error instanceof ApiError)) {
    return { kind: 'other', message: 'Something went wrong. Try again.' }
  }
  switch (error.problem) {
    case 'payment-declined':
      return { kind: 'declined' }
    case 'insufficient-stock':
      return { kind: 'short', items: itemsOf<ShortItem>(error) }
    case 'product-not-sellable':
      return { kind: 'unsellable', items: itemsOf<UnsellableItem>(error) }
    case 'network-error':
      return { kind: 'unreachable' }
    default:
      return error.isServerError
        ? { kind: 'busy' }
        : { kind: 'other', message: error.detail ?? error.title }
  }
}

function fixedCart(lines: CartLine[], outcome: Outcome): CartLine[] {
  if (outcome.kind === 'short') {
    return outcome.items.reduce(
      (current, item) => withQuantity(current, item.sku, item.available),
      lines,
    )
  }
  if (outcome.kind === 'unsellable') {
    return outcome.items.reduce((current, item) => withoutLine(current, item.sku), lines)
  }
  return lines
}

function OutcomeAlert({
  outcome,
  names,
  onFix,
}: {
  outcome: Outcome
  names: Map<string, string>
  onFix: () => void
}) {
  const name = (sku: string) => names.get(sku) ?? sku
  const fix = (
    <button type="button" className={styles.secondary} onClick={onFix}>
      Fix my cart
    </button>
  )
  switch (outcome.kind) {
    case 'declined':
      return (
        <div role="alert" className={styles.alert}>
          <p>
            <strong>Your card was declined.</strong>
          </p>
          <p>Nothing was charged and nothing was taken from stock. Try another card.</p>
        </div>
      )
    case 'short':
      return (
        <div role="alert" className={styles.alert}>
          <p>
            <strong>Some items are no longer available in that quantity.</strong>
          </p>
          <ul>
            {outcome.items.map((item) => (
              <li key={item.sku}>
                {`${name(item.sku)}: you asked for ${item.requested}, ${item.available} available.`}
              </li>
            ))}
          </ul>
          {fix}
        </div>
      )
    case 'unsellable':
      return (
        <div role="alert" className={styles.alert}>
          <p>
            <strong>Some items can't be bought right now.</strong>
          </p>
          <ul>
            {outcome.items.map((item) => (
              <li
                key={item.sku}
              >{`${name(item.sku)} ${REASONS[item.reason] ?? 'is unavailable'}.`}</li>
            ))}
          </ul>
          {fix}
        </div>
      )
    case 'unreachable':
      return (
        <p role="alert" className={styles.alert}>
          The shop could not be reached. Press Pay again: you won&apos;t be charged twice.
        </p>
      )
    case 'busy':
      return (
        <p role="alert" className={styles.alert}>
          The shop is busy right now. Press Pay again: you won&apos;t be charged twice.
        </p>
      )
    default:
      return (
        <p role="alert" className={styles.alert}>
          {outcome.message}
        </p>
      )
  }
}

function Summary({ quote }: { quote: Quote }) {
  return (
    <section aria-label="Order summary" className={styles.summary}>
      <ul className={styles.summaryLines}>
        {quote.lines.map((line) => (
          <li key={line.sku}>
            <span>
              {line.quantity} × {line.name}
            </span>
            <span>{line.line_total ? formatPrice(line.line_total, quote.currency) : ''}</span>
          </li>
        ))}
      </ul>
      <p className={styles.total}>{`Total: ${formatPrice(quote.total, quote.currency)}`}</p>
    </section>
  )
}

function CheckoutForm({ quote, lines }: { quote: Quote; lines: CartLine[] }) {
  const cart = useCart()
  const navigate = useNavigate()
  const client = useQueryClient()
  const place = usePlaceOrder()
  const paid = quote.payment_required
  const [outcome, setOutcome] = useState<Outcome | null>(null)
  const [problems, setProblems] = useState<FieldProblem[]>([])
  const attempt = useRef<Attempt | null>(null)
  const sending = useRef(false)
  const {
    register,
    handleSubmit,
    setError,
    setValue,
    formState: { errors },
  } = useForm<CheckoutValues>({
    resolver: zodResolver(paid ? paidCheckoutSchema : freeCheckoutSchema),
    defaultValues: emptyCheckout,
  })
  const names = new Map(lines.map((line) => [line.sku.toUpperCase(), line.name]))

  const showFieldErrors = (error: ApiError) => {
    const known = new Set<string>(CHECKOUT_FIELDS)
    const unmatched: FieldProblem[] = []
    let focused = false
    for (const problem of error.errors) {
      const field = SERVER_FIELD_ALIASES[problem.field] ?? problem.field
      if (known.has(field)) {
        setError(
          field as FieldPath<CheckoutValues>,
          { type: problem.code, message: problem.message },
          { shouldFocus: !focused },
        )
        focused = true
      } else {
        unmatched.push(problem)
      }
    }
    setProblems(unmatched)
  }

  const submit = (values: CheckoutValues) => {
    if (sending.current) {
      return
    }
    const body = checkoutBody(values, requestedLines(lines), paid)
    const request = JSON.stringify(body)
    if (attempt.current === null || attempt.current.request !== request) {
      attempt.current = { key: newIdempotencyKey(), request }
    }
    sending.current = true
    setOutcome(null)
    setProblems([])
    place.mutate(
      { body, key: attempt.current.key },
      {
        onSuccess: (order) => {
          attempt.current = null
          client.setQueryData(orderKeys.detail(order.id), order)
          void navigate(`/orders/${order.id}`, { replace: true })
          cart.clear()
        },
        onError: (error) => {
          const next = outcomeOf(error)
          if (next.kind === 'declined') {
            attempt.current = null
            setValue('payment.card_number', '')
            setValue('payment.expiry', '')
            setValue('payment.cvc', '')
          }
          if (error instanceof ApiError && error.isValidation) {
            showFieldErrors(error)
            return
          }
          setOutcome(next)
        },
        onSettled: () => {
          sending.current = false
        },
      },
    )
  }

  const fixCart = () => {
    if (outcome !== null) {
      const fixed = outcome
      cart.update((current) => fixedCart(current, fixed))
    }
    void navigate('/cart')
  }

  return (
    <form noValidate onSubmit={(event) => void handleSubmit(submit)(event)} className={styles.form}>
      {outcome !== null ? <OutcomeAlert outcome={outcome} names={names} onFix={fixCart} /> : null}
      <fieldset className={styles.fieldset}>
        <legend>Your details</legend>
        <TextField
          label="Name"
          autoComplete="name"
          error={errors.customer?.name}
          {...register('customer.name')}
        />
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          error={errors.customer?.email}
          {...register('customer.email')}
        />
      </fieldset>
      {paid ? (
        <fieldset className={styles.fieldset}>
          <legend>Card</legend>
          <TextField
            label="Card number"
            inputMode="numeric"
            autoComplete="cc-number"
            hint="Test cards: 4242 4242 4242 4242 is approved, 4000 0000 0000 0002 is declined."
            error={errors.payment?.card_number}
            {...register('payment.card_number')}
          />
          <div className={styles.cardRow}>
            <TextField
              label="Expiry (MM/YY)"
              autoComplete="cc-exp"
              placeholder="MM/YY"
              error={errors.payment?.expiry}
              {...register('payment.expiry')}
            />
            <TextField
              label="CVC"
              inputMode="numeric"
              autoComplete="cc-csc"
              error={errors.payment?.cvc}
              {...register('payment.cvc')}
            />
          </div>
        </fieldset>
      ) : (
        <p className={formStyles.hint}>This order is free. No card is needed.</p>
      )}
      <FormProblems problems={problems} />
      <button type="submit" className={styles.primary} disabled={place.isPending}>
        {paid ? `Pay ${formatPrice(quote.total, quote.currency)}` : 'Place free order'}
      </button>
    </form>
  )
}

export function CheckoutPage() {
  const cart = useCart()
  const quote = useQuote(cart.lines)

  if (cart.lines.length === 0) {
    return (
      <section aria-labelledby="checkout-title" className={styles.page}>
        <h2 id="checkout-title">Checkout</h2>
        <p>Your cart is empty.</p>
        <p>
          <Link to="/">Continue shopping</Link>
        </p>
      </section>
    )
  }
  if (quote.isError) {
    return (
      <section aria-labelledby="checkout-title" className={styles.page}>
        <h2 id="checkout-title">Checkout</h2>
        <p role="alert" className={styles.alert}>
          The prices could not be loaded. Try again in a moment.
        </p>
      </section>
    )
  }
  if (quote.data === undefined || quote.isPlaceholderData) {
    return <p>Loading…</p>
  }
  return (
    <section aria-labelledby="checkout-title" className={styles.page}>
      <h2 id="checkout-title">Checkout</h2>
      <Summary quote={quote.data} />
      {quote.data.ready ? (
        <CheckoutForm quote={quote.data} lines={cart.lines} />
      ) : (
        <div className={styles.alert}>
          <p>Some items in your cart need attention.</p>
          <p>
            <Link to="/cart">Back to the cart</Link>
          </p>
        </div>
      )}
    </section>
  )
}

import { Link, useParams } from 'react-router'

import { ApiError } from '../../../api/apiError'
import type { Order } from '../../../api/orders'
import { useSession } from '../../../session/session'
import { formatDateTime, formatPrice } from '../../admin/products/format'
import styles from './Checkout.module.css'
import { useOrder } from './orderQueries'

export function Lines({ order }: { order: Order }) {
  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th scope="col">Product</th>
          <th scope="col">Price</th>
          <th scope="col">Quantity</th>
          <th scope="col">Line total</th>
        </tr>
      </thead>
      <tbody>
        {order.lines.map((line) => (
          <tr key={line.sku}>
            <td>
              {line.name} <span className={styles.muted}>{line.sku}</span>
            </td>
            <td>{formatPrice(line.unit_price, order.currency)}</td>
            <td>{line.quantity}</td>
            <td>{formatPrice(line.line_total, order.currency)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function Details({ order }: { order: Order }) {
  return (
    <dl className={styles.details}>
      <dt>Order number</dt>
      <dd>{order.id}</dd>
      <dt>Placed</dt>
      <dd>{formatDateTime(order.created_at)} UTC</dd>
      <dt>Email</dt>
      <dd>{order.customer.email}</dd>
      {order.payment_reference ? (
        <>
          <dt>Payment reference</dt>
          <dd>{order.payment_reference}</dd>
        </>
      ) : null}
    </dl>
  )
}

function PaidOrder({ order }: { order: Order }) {
  const session = useSession()
  const buyer = session.data?.role === 'BUYER'
  return (
    <section aria-labelledby="order-title" className={styles.page}>
      <h2 id="order-title">Thank you, {order.customer.name}</h2>
      <p className={styles.success}>Your order is paid.</p>
      <Lines order={order} />
      <p className={styles.total}>{`Total: ${formatPrice(order.total, order.currency)}`}</p>
      <p>
        {order.card_last4
          ? `Paid with the card ending in ${order.card_last4}.`
          : 'No card was needed: this order was free.'}
      </p>
      <Details order={order} />
      <p>
        <Link to="/">Continue shopping</Link>
        {buyer ? (
          <>
            {' · '}
            <Link to="/account/orders">See My orders</Link>
          </>
        ) : null}
      </p>
    </section>
  )
}

function DeclinedOrder({ order }: { order: Order }) {
  return (
    <section aria-labelledby="order-title" className={styles.page}>
      <h2 id="order-title">Payment declined</h2>
      <p role="alert" className={styles.alert}>
        This payment was declined. Nothing was charged and nothing was taken from stock.
      </p>
      <Lines order={order} />
      <Details order={order} />
      <p>
        <Link to="/cart">Back to the cart</Link>
      </p>
    </section>
  )
}

export function OrderConfirmationPage() {
  const { orderId = '' } = useParams()
  const order = useOrder(orderId)

  if (order.isPending) {
    return <p>Loading…</p>
  }
  if (order.isError) {
    const missing = order.error instanceof ApiError && order.error.problem === 'not-found'
    return (
      <div role="alert" className={styles.alert}>
        <p>{missing ? 'This order was not found.' : 'The order could not be loaded.'}</p>
        <p>
          <Link to="/">Back to the shop</Link>
        </p>
      </div>
    )
  }
  return order.data.status === 'PAYMENT_FAILED' ? (
    <DeclinedOrder order={order.data} />
  ) : (
    <PaidOrder order={order.data} />
  )
}

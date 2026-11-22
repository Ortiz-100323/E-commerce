import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router'

import { ordersApi, type Order } from '../../api/orders'
import { formatDateTime, formatPrice } from '../admin/products/format'
import styles from './Account.module.css'
import { RequireRole } from './RequireRole'

const STATUS_TEXT: Record<Order['status'], string> = {
  PAID: 'Paid',
  PENDING: 'Processing',
  PAYMENT_FAILED: 'Payment declined',
}

function shortNumber(id: string): string {
  return id.slice(0, 8).toUpperCase()
}

function items(order: Order): string {
  const count = order.lines.reduce((sum, line) => sum + line.quantity, 0)
  const names = order.lines.map((line) => line.name).join(', ')
  return `${count} ${count === 1 ? 'item' : 'items'}: ${names}`
}

function OrderRow({ order }: { order: Order }) {
  return (
    <li className={styles.order} aria-label={`Order ${shortNumber(order.id)}`}>
      <h2 className={styles.orderTitle}>
        <Link to={`/orders/${order.id}`}>Order {shortNumber(order.id)}</Link>
      </h2>
      <p className={styles.orderTotal}>{formatPrice(order.total, order.currency)}</p>
      <p className={styles.orderMeta}>{formatDateTime(order.created_at)} UTC</p>
      <span
        className={
          order.status === 'PAYMENT_FAILED'
            ? `${styles.status} ${styles.statusFailed}`
            : styles.status
        }
      >
        {STATUS_TEXT[order.status]}
      </span>
      <p className={styles.orderItems}>{items(order)}</p>
    </li>
  )
}

function MyOrders() {
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get('page')) || 1)
  const orders = useQuery({
    queryKey: ['my-orders', page],
    queryFn: () => ordersApi.mine(page),
    placeholderData: (previous) => previous,
  })
  const data = orders.data
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <section aria-labelledby="my-orders-title" className={styles.page}>
      <h1 id="my-orders-title">My orders</h1>
      {orders.isPending ? <p>Loading your orders…</p> : null}
      {data && data.total === 0 ? (
        <div className={styles.denied}>
          <h2 className={styles.panelTitle}>No orders yet</h2>
          <p>Orders you place while logged in show up here.</p>
          <Link to="/" className={styles.homeLink}>
            Start shopping
          </Link>
        </div>
      ) : null}
      {data && data.items.length > 0 ? (
        <ul className={styles.orders} aria-label="Orders">
          {data.items.map((order) => (
            <OrderRow key={order.id} order={order} />
          ))}
        </ul>
      ) : null}
      {data && data.total > data.page_size ? (
        <nav aria-label="Pages" className={styles.pager}>
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setParams({ page: String(page - 1) })}
          >
            Previous
          </button>
          <span>
            Page {page} of {pages}
          </span>
          <button
            type="button"
            disabled={page >= pages}
            onClick={() => setParams({ page: String(page + 1) })}
          >
            Next
          </button>
        </nav>
      ) : null}
    </section>
  )
}

export function MyOrdersPage() {
  return (
    <RequireRole role="BUYER">
      <MyOrders />
    </RequireRole>
  )
}

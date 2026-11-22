import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'

import { ApiError } from '../../../api/apiError'
import { adminOrdersApi } from '../../../api/orders'
import { Details, Lines } from '../../storefront/checkout/OrderConfirmationPage'
import { formatPrice } from '../products/format'
import { AccountBadge, orderNumber, StatusBadge } from './AdminOrdersPage'
import styles from './Orders.module.css'

export function AdminOrderPage() {
  const { orderId = '' } = useParams()
  const order = useQuery({
    queryKey: ['admin-order', orderId],
    queryFn: () => adminOrdersApi.get(orderId),
    meta: { handledProblems: ['not-found', 'validation-error'] },
    retry: false,
  })

  if (order.isPending) {
    return <p>Loading the order…</p>
  }
  if (order.isError) {
    const missing =
      order.error instanceof ApiError && (order.error.status === 404 || order.error.status === 422)
    return (
      <section aria-labelledby="admin-order-title" className={styles.empty}>
        <h2 id="admin-order-title" className={styles.emptyTitle}>
          {missing ? 'Order not found' : "The order couldn't be loaded."}
        </h2>
        <Link to="/admin/orders" className={styles.clear}>
          Back to all orders
        </Link>
      </section>
    )
  }

  const item = order.data
  return (
    <section aria-labelledby="admin-order-title" className={styles.detail}>
      <p className={styles.back}>
        <Link to="/admin/orders">‹ All orders</Link>
      </p>
      <div className={styles.detailHeader}>
        <h2 id="admin-order-title">Order {orderNumber(item.id)}</h2>
        <StatusBadge status={item.status} />
        <AccountBadge order={item} />
      </div>
      <p className={styles.customerLine}>
        <strong>{item.customer.name}</strong> · {item.customer.email}
      </p>
      <Lines order={item} />
      <p className={styles.total}>Total: {formatPrice(item.total, item.currency)}</p>
      <p>
        {item.status === 'PAYMENT_FAILED'
          ? `The card ending in ${item.card_last4 ?? '????'} was declined (${item.decline_reason ?? 'no reason given'}). Nothing was charged.`
          : item.card_last4
            ? `Paid with the card ending in ${item.card_last4}.`
            : 'No card was needed: this order was free.'}
      </p>
      <Details order={item} />
    </section>
  )
}

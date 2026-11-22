import { useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'

import { adminOrdersApi, type AdminOrder, type OrderStatus } from '../../../api/orders'
import { formatDateTime, formatPrice } from '../products/format'
import styles from './Orders.module.css'

export const STATUS_TEXT: Record<OrderStatus, string> = {
  PAID: 'Paid',
  PENDING: 'Processing',
  PAYMENT_FAILED: 'Payment declined',
}

const STATUSES: { value: '' | OrderStatus; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'PAID', label: 'Paid' },
  { value: 'PAYMENT_FAILED', label: 'Payment declined' },
  { value: 'PENDING', label: 'Processing' },
]

export function orderNumber(id: string): string {
  return id.slice(0, 8).toUpperCase()
}

export function StatusBadge({ status }: { status: OrderStatus }) {
  return (
    <span className={status === 'PAYMENT_FAILED' ? styles.failed : styles.badge}>
      {STATUS_TEXT[status]}
    </span>
  )
}

export function AccountBadge({ order }: { order: AdminOrder }) {
  return order.customer_account ? (
    <span className={styles.account}>Customer account</span>
  ) : (
    <span className={styles.guest}>Guest</span>
  )
}

function itemCount(order: AdminOrder): number {
  return order.lines.reduce((sum, line) => sum + line.quantity, 0)
}

function OrderRow({ order }: { order: AdminOrder }) {
  const navigate = useNavigate()
  const open = () => void navigate(`/admin/orders/${order.id}`)
  return (
    <tr aria-label={`Order ${orderNumber(order.id)}`} className={styles.row} onClick={open}>
      <td data-label="Order">
        <Link to={`/admin/orders/${order.id}`} onClick={(event) => event.stopPropagation()}>
          {orderNumber(order.id)}
        </Link>
      </td>
      <td data-label="Date">{formatDateTime(order.created_at)}</td>
      <td data-label="Customer">
        <span className={styles.who}>
          <span className={styles.customer}>{order.customer.name}</span>
          <span className={styles.email}>{order.customer.email}</span>
        </span>
      </td>
      <td data-label="Type">
        <AccountBadge order={order} />
      </td>
      <td data-label="Items" className={styles.number}>
        {itemCount(order)}
      </td>
      <td data-label="Total" className={styles.number}>
        {formatPrice(order.total, order.currency)}
      </td>
      <td data-label="Status">
        <StatusBadge status={order.status} />
      </td>
    </tr>
  )
}

function Filters({ q, status }: { q: string; status: string }) {
  const [, setParams] = useSearchParams()
  const [text, setText] = useState(q)
  const apply = (next: { q?: string; status?: string }) => {
    const params = new URLSearchParams()
    const query = (next.q ?? text).trim()
    const state = next.status ?? status
    if (query) {
      params.set('q', query)
    }
    if (state) {
      params.set('status', state)
    }
    setParams(params)
  }
  const submit = (event: FormEvent) => {
    event.preventDefault()
    apply({})
  }
  return (
    <form role="search" onSubmit={submit} className={styles.filters}>
      <label className={styles.searchField}>
        Search
        <input
          type="search"
          value={text}
          placeholder="Customer name, email or order number"
          onChange={(event) => setText(event.target.value)}
        />
      </label>
      <button type="submit">Search</button>
      <label>
        Status
        <select value={status} onChange={(event) => apply({ status: event.target.value })}>
          {STATUSES.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
    </form>
  )
}

export function AdminOrdersPage() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const rawStatus = params.get('status') ?? ''
  const status = STATUSES.some((option) => option.value === rawStatus) ? rawStatus : ''
  const page = Math.max(1, Number(params.get('page')) || 1)
  const orders = useQuery({
    queryKey: ['admin-orders', q, status, page],
    queryFn: () =>
      adminOrdersApi.list({
        q: q || undefined,
        status: (status || undefined) as OrderStatus | undefined,
        page,
      }),
    placeholderData: (previous) => previous,
  })
  const data = orders.data
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  const goTo = (next: number) => {
    const copy = new URLSearchParams(params)
    copy.set('page', String(next))
    setParams(copy)
  }

  return (
    <section aria-labelledby="admin-orders-title">
      <h2 id="admin-orders-title">Orders</h2>
      <Filters key={`${q}|${status}`} q={q} status={status} />
      {orders.isPending ? <p>Loading the orders…</p> : null}
      {data && data.total === 0 ? (
        <div className={styles.empty}>
          <p className={styles.emptyTitle}>No orders match.</p>
          {q || status ? (
            <Link to="/admin/orders" className={styles.clear}>
              Clear filters
            </Link>
          ) : (
            <p>Orders appear here as soon as customers buy.</p>
          )}
        </div>
      ) : null}
      {data && data.items.length > 0 ? (
        <>
          <p className={styles.summary}>
            {data.total} {data.total === 1 ? 'order' : 'orders'}
          </p>
          <div className={styles.tableWrap}>
            <table className={styles.table} aria-label="Orders">
              <thead>
                <tr>
                  <th scope="col">Order</th>
                  <th scope="col">Date (UTC)</th>
                  <th scope="col">Customer</th>
                  <th scope="col">Type</th>
                  <th scope="col" className={styles.number}>
                    Items
                  </th>
                  <th scope="col" className={styles.number}>
                    Total
                  </th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((order) => (
                  <OrderRow key={order.id} order={order} />
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
      {data && data.total > data.page_size ? (
        <nav aria-label="Pages" className={styles.pager}>
          <button type="button" disabled={page <= 1} onClick={() => goTo(page - 1)}>
            Previous
          </button>
          <span>
            Page {page} of {pages}
          </span>
          <button type="button" disabled={page >= pages} onClick={() => goTo(page + 1)}>
            Next
          </button>
        </nav>
      ) : null}
    </section>
  )
}

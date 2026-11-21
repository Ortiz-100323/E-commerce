import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'

import type { Product, ProductQuery } from '../../../api/products'
import { ConfirmDialog } from '../../../components/ConfirmDialog'
import { useNotify } from '../../../notifications/NotificationContext'
import { formatPrice } from './format'
import styles from './Products.module.css'
import { useArchiveProduct, useProductList, useRestoreProduct } from './queries'

export const PAGE_SIZE = 20

const STATUSES = [
  { value: 'ACTIVE', label: 'Active' },
  { value: 'ARCHIVED', label: 'Archived' },
  { value: 'ALL', label: 'All' },
] as const

type StatusValue = (typeof STATUSES)[number]['value']

function statusOf(raw: string | null): StatusValue {
  return STATUSES.find((status) => status.value === raw)?.value ?? 'ACTIVE'
}

function pageOf(raw: string | null): number {
  const page = Number(raw)
  return Number.isInteger(page) && page >= 1 ? page : 1
}

export function ProductsTablePage() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const status = statusOf(params.get('status'))
  const page = pageOf(params.get('page'))
  const query: ProductQuery = { q, status, page, page_size: PAGE_SIZE, sort: 'name' }
  const list = useProductList(query)
  const archive = useArchiveProduct()
  const restore = useRestoreProduct()
  const notify = useNotify()
  const [search, setSearch] = useState(q)
  const [archiving, setArchiving] = useState<Product | null>(null)
  const busy = archive.isPending || restore.isPending

  const update = (changes: Record<string, string>) => {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(changes)) {
      if (
        value === '' ||
        (key === 'status' && value === 'ACTIVE') ||
        (key === 'page' && value === '1')
      ) {
        next.delete(key)
      } else {
        next.set(key, value)
      }
    }
    setParams(next)
  }

  const onSearch = (event: FormEvent) => {
    event.preventDefault()
    update({ q: search.trim(), page: '1' })
  }

  const confirmArchive = () => {
    if (archiving === null || busy) {
      return
    }
    const product = archiving
    archive.mutate(product.id, {
      onSuccess: () => notify({ title: 'Product archived', detail: product.sku, tone: 'success' }),
      onSettled: () => setArchiving(null),
    })
  }

  const onRestore = (product: Product) => {
    if (busy) {
      return
    }
    restore.mutate(product.id, {
      onSuccess: () => notify({ title: 'Product restored', detail: product.sku, tone: 'success' }),
    })
  }

  const data = list.data
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <section aria-labelledby="admin-products-title">
      <div className={styles.toolbar}>
        <h2 id="admin-products-title">Products</h2>
        <Link to="/admin/products/new" className={styles.primaryLink}>
          New product
        </Link>
      </div>
      <form role="search" onSubmit={onSearch} className={styles.filters}>
        <label>
          Search
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Name, SKU or description"
          />
        </label>
        <button type="submit">Search</button>
        <label>
          Status
          <select
            value={status}
            onChange={(event) => update({ status: event.target.value, page: '1' })}
          >
            {STATUSES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </form>

      {list.isPending ? <p>Loading products…</p> : null}
      {list.isError && !data ? (
        <p>
          We couldn't load the products.{' '}
          <button type="button" onClick={() => void list.refetch()}>
            Try again
          </button>
        </p>
      ) : null}

      {data && data.items.length === 0 ? <p>No products match.</p> : null}

      {data && data.items.length > 0 ? (
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">SKU</th>
              <th scope="col">Name</th>
              <th scope="col">Category</th>
              <th scope="col" className={styles.number}>
                Price
              </th>
              <th scope="col" className={styles.number}>
                Stock
              </th>
              <th scope="col">Status</th>
              <th scope="col">
                <span className={styles.hidden}>Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((product) => (
              <tr key={product.id} aria-label={product.sku}>
                <td>{product.sku}</td>
                <td>
                  {product.name}
                  {product.gift ? <span className={styles.badge}>Gift</span> : null}
                </td>
                <td>{product.category}</td>
                <td className={styles.number}>{formatPrice(product.price, product.currency)}</td>
                <td className={styles.number}>
                  {product.stock}
                  {product.stock === 0 ? (
                    <span className={styles.warning}>Out of stock</span>
                  ) : null}
                </td>
                <td>{product.status === 'ACTIVE' ? 'Active' : 'Archived'}</td>
                <td className={styles.rowActions}>
                  <Link to={`/admin/products/${product.id}/edit`}>Edit</Link>
                  <Link to={`/admin/products/${product.id}/history`}>History</Link>
                  {product.status === 'ACTIVE' ? (
                    <button type="button" onClick={() => setArchiving(product)} disabled={busy}>
                      Archive
                    </button>
                  ) : (
                    <button type="button" onClick={() => onRestore(product)} disabled={busy}>
                      Restore
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}

      {data && data.total > 0 ? (
        <nav aria-label="Pages" className={styles.pager}>
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => update({ page: String(page - 1) })}
          >
            Previous
          </button>
          <span>
            Page {data.page} of {pages} · {data.total} {data.total === 1 ? 'product' : 'products'}
          </span>
          <button
            type="button"
            disabled={page >= pages}
            onClick={() => update({ page: String(page + 1) })}
          >
            Next
          </button>
        </nav>
      ) : null}

      {archiving ? (
        <ConfirmDialog
          title={`Archive ${archiving.name}?`}
          message="It will be hidden from the shop. You can restore it at any time."
          confirmLabel="Archive"
          cancelLabel="Cancel"
          busy={busy}
          onConfirm={confirmArchive}
          onCancel={() => setArchiving(null)}
        />
      ) : null}
    </section>
  )
}

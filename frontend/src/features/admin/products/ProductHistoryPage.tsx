import { Link, useParams } from 'react-router'

import type { HistoryEntry } from '../../../api/products'
import { eventLabel, fieldLabel, formatDateTime, formatValue } from './format'
import { ProductMissing } from './ProductMissing'
import styles from './Products.module.css'
import { useProduct, useProductHistory } from './queries'

function changedFields(entry: HistoryEntry): string[] {
  const names = new Set([...Object.keys(entry.before ?? {}), ...Object.keys(entry.after ?? {})])
  return [...names]
}

function EntryDetails({ entry }: { entry: HistoryEntry }) {
  const fields = changedFields(entry)
  const context = Object.entries(entry.context)
  return (
    <dl className={styles.changes}>
      {fields.map((field) => (
        <div key={field} className={styles.change}>
          <dt>{fieldLabel(field)}</dt>
          <dd>
            {entry.before === null ? (
              formatValue(entry.after?.[field])
            ) : (
              <>
                <span className={styles.before}>{formatValue(entry.before[field])}</span>
                {' → '}
                <span>{formatValue(entry.after?.[field])}</span>
              </>
            )}
          </dd>
        </div>
      ))}
      {context.map(([key, value]) => (
        <div key={key} className={styles.change}>
          <dt>{fieldLabel(key)}</dt>
          <dd>{formatValue(value)}</dd>
        </div>
      ))}
    </dl>
  )
}

export function ProductHistoryPage() {
  const { productId = '' } = useParams()
  const product = useProduct(productId)
  const history = useProductHistory(productId)

  if (product.isPending || history.isPending) {
    return <p>Loading…</p>
  }
  if (product.isError || history.isError) {
    return (
      <ProductMissing
        error={product.error ?? history.error}
        onRetry={() => {
          void product.refetch()
          void history.refetch()
        }}
      />
    )
  }
  return (
    <section aria-labelledby="history-title">
      <h2 id="history-title">
        History of {product.data.sku} · {product.data.name}
      </h2>
      <p>
        <Link to="/admin/products">Back to the products</Link>
      </p>
      {history.data.entries.length === 0 ? (
        <p>No changes recorded yet.</p>
      ) : (
        <ol className={styles.timeline} aria-label="Changes, oldest first">
          {history.data.entries.map((entry, index) => (
            <li key={`${entry.occurred_at}-${index}`} className={styles.entry}>
              <p className={styles.entryHeader}>
                <strong>{eventLabel(entry.event)}</strong> by {entry.actor} ·{' '}
                <time dateTime={entry.occurred_at}>{formatDateTime(entry.occurred_at)} UTC</time>
              </p>
              <EntryDetails entry={entry} />
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

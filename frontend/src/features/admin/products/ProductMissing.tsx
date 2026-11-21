import { Link } from 'react-router'

import { ApiError } from '../../../api/apiError'

type ProductMissingProps = {
  error: unknown
  onRetry: () => void
}

export function ProductMissing({ error, onRetry }: ProductMissingProps) {
  if (error instanceof ApiError && error.status === 404) {
    return (
      <section aria-labelledby="missing-title">
        <h2 id="missing-title">Product not found</h2>
        <p>
          This product doesn't exist. <Link to="/admin/products">Back to the products</Link>
        </p>
      </section>
    )
  }
  return (
    <section aria-labelledby="missing-title">
      <h2 id="missing-title">We couldn't load this product.</h2>
      <p>
        <button type="button" onClick={onRetry}>
          Try again
        </button>{' '}
        <Link to="/admin/products">Back to the products</Link>
      </p>
    </section>
  )
}

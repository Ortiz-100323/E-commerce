import { Link } from 'react-router'

export function NotFoundPage() {
  return (
    <section aria-labelledby="not-found-title">
      <h1 id="not-found-title">Page not found</h1>
      <p>
        This page doesn't exist. <Link to="/">Go to the shop</Link>
      </p>
    </section>
  )
}

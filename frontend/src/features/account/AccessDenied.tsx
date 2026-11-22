import { Link } from 'react-router'

import styles from './Account.module.css'

export function AccessDenied({ title, message }: { title: string; message: string }) {
  return (
    <section aria-labelledby="denied-title" className={styles.denied}>
      <h1 id="denied-title">{title}</h1>
      <p>{message}</p>
      <Link to="/" className={styles.homeLink}>
        Back to the shop
      </Link>
    </section>
  )
}

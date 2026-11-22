import { Link, useNavigate } from 'react-router'

import { useLogOut } from '../../session/session'
import styles from './Account.module.css'

export function AdminCannotBuy() {
  const logOut = useLogOut()
  const navigate = useNavigate()
  return (
    <section aria-labelledby="no-shopping-title" className={styles.denied}>
      <h1 id="no-shopping-title">Administrator accounts can&apos;t place orders</h1>
      <p>
        Log out to shop as a guest, or use a customer account. You can see every order in Orders.
      </p>
      <p className={styles.deniedActions}>
        <Link to="/admin/orders" className={styles.homeLink}>
          See all orders
        </Link>
        <button
          type="button"
          className={styles.homeLink}
          onClick={() => {
            void navigate('/', { replace: true })
            logOut.mutate()
          }}
        >
          Log out
        </button>
      </p>
    </section>
  )
}

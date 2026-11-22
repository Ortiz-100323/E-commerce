import { NavLink, Outlet } from 'react-router'

import { useCart } from '../cart/CartContext'
import styles from './AppShell.module.css'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  isActive ? `${styles.link} ${styles.active}` : styles.link

export function AppShell() {
  const { count } = useCart()
  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <NavLink to="/" className={styles.brand} end>
          E-commerce
        </NavLink>
        <nav aria-label="Main" className={styles.nav}>
          <NavLink to="/" className={linkClass} end>
            Shop
          </NavLink>
          <NavLink to="/admin" className={linkClass}>
            Admin
          </NavLink>
        </nav>
        <p className={styles.cart} aria-live="polite">
          <NavLink to="/cart" className={linkClass}>
            {`Cart: ${count} ${count === 1 ? 'item' : 'items'}`}
          </NavLink>
        </p>
      </header>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}

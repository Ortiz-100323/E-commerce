import { NavLink, Outlet } from 'react-router'

import { useCart } from '../cart/CartContext'
import controls from '../styles/controls.module.css'
import styles from './AppShell.module.css'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  isActive ? `${styles.link} ${styles.active}` : styles.link

function BagIcon() {
  return (
    <svg
      className={styles.bag}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M5 8h14l-1.2 11.1a2 2 0 0 1-2 1.9H8.2a2 2 0 0 1-2-1.9L5 8Z" />
      <path d="M9 10V6.5a3 3 0 0 1 6 0V10" />
    </svg>
  )
}

export function AppShell() {
  const { count } = useCart()
  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={styles.bar}>
          <NavLink to="/" className={styles.brand} end>
            <span className={styles.mark} aria-hidden="true" />
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
            <NavLink
              to="/cart"
              aria-label={`Cart: ${count} ${count === 1 ? 'item' : 'items'}`}
              className={({ isActive }) =>
                isActive ? `${styles.cartLink} ${styles.cartActive}` : styles.cartLink
              }
            >
              <BagIcon />
              Cart<span className={controls.visuallyHidden}>: </span>
              <span className={count > 0 ? styles.count : `${styles.count} ${styles.empty}`}>
                {count}
              </span>
              <span className={controls.visuallyHidden}>{count === 1 ? ' item' : ' items'}</span>
            </NavLink>
          </p>
        </div>
      </header>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}

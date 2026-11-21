import { NavLink, Outlet } from 'react-router'

import styles from './AppShell.module.css'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  isActive ? `${styles.link} ${styles.active}` : styles.link

export function AppShell() {
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
      </header>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}

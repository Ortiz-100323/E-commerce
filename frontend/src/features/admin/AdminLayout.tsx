import { Link, NavLink, Outlet, useLocation } from 'react-router'

import { useSession } from '../../session/session'
import { RequireRole } from '../account/RequireRole'
import styles from './AdminLayout.module.css'

function AdminArea() {
  const session = useSession()
  const { pathname } = useLocation()
  const importing = pathname.startsWith('/admin/imports')

  return (
    <section aria-labelledby="admin-title">
      <div className={styles.bar}>
        <h1 id="admin-title">Admin</h1>
        <p className={styles.reviewer}>
          Signed in as <strong>{session.data?.name}</strong>
        </p>
      </div>
      <nav aria-label="Admin" className={styles.nav}>
        <NavLink to="/admin/products">Products</NavLink>
        <Link to="/admin/imports/new" aria-current={importing ? 'page' : undefined}>
          Import CSV
        </Link>
        <NavLink to="/admin/accounts">Admins</NavLink>
      </nav>
      <Outlet />
    </section>
  )
}

export function AdminLayout() {
  return (
    <RequireRole role="ADMIN">
      <AdminArea />
    </RequireRole>
  )
}

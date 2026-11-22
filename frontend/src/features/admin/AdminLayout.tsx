import { useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router'

import { useActor } from '../../actor/ActorContext'
import { ActorPrompt } from '../../actor/ActorPrompt'
import styles from './AdminLayout.module.css'

export function AdminLayout() {
  const { actor, setActor } = useActor()
  const [changing, setChanging] = useState(false)
  const { pathname } = useLocation()
  const importing = pathname.startsWith('/admin/imports')

  if (actor === null) {
    return <ActorPrompt onSave={setActor} />
  }

  return (
    <section aria-labelledby="admin-title">
      <div className={styles.bar}>
        <h1 id="admin-title">Admin</h1>
        <p className={styles.reviewer}>
          Reviewing as <strong>{actor}</strong>{' '}
          <button type="button" className={styles.change} onClick={() => setChanging(true)}>
            Change
          </button>
        </p>
      </div>
      <nav aria-label="Admin" className={styles.nav}>
        <NavLink to="/admin/products">Products</NavLink>
        <Link to="/admin/imports/new" aria-current={importing ? 'page' : undefined}>
          Import CSV
        </Link>
      </nav>
      <Outlet />
      {changing ? (
        <ActorPrompt
          initialName={actor}
          onSave={(name) => {
            setActor(name)
            setChanging(false)
          }}
          onCancel={() => setChanging(false)}
        />
      ) : null}
    </section>
  )
}

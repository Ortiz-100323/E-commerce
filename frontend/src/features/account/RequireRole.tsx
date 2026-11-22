import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'

import type { Role } from '../../api/session'
import { useSession } from '../../session/session'
import { AccessDenied } from './AccessDenied'

const DENIED: Record<Role, { title: string; message: string }> = {
  ADMIN: {
    title: 'This area is for administrators',
    message: 'Your account is a customer account, so the admin pages are not available to it.',
  },
  BUYER: {
    title: 'My orders is for customer accounts',
    message: 'Administrator accounts have no orders of their own.',
  },
}

export function RequireRole({ role, children }: { role: Role; children: ReactNode }) {
  const session = useSession()
  const location = useLocation()

  if (session.isPending) {
    return <p>Loading…</p>
  }
  if (!session.data) {
    const next = `${location.pathname}${location.search}`
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />
  }
  if (session.data.role !== role) {
    return <AccessDenied {...DENIED[role]} />
  }
  return children
}

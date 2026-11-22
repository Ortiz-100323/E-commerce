import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'

import type { NoticeContent } from './describeProblem'
import styles from './Notifications.module.css'

export const SUCCESS_NOTICE_MS = 5000

type Notice = NoticeContent & { id: number }

type NotificationApi = {
  notify: (notice: NoticeContent) => void
}

const NotificationContext = createContext<NotificationApi | null>(null)

function NoticeItem({ notice, onDismiss }: { notice: Notice; onDismiss: (id: number) => void }) {
  const success = notice.tone === 'success'
  const { id } = notice

  useEffect(() => {
    if (!success) {
      return undefined
    }
    const timer = window.setTimeout(() => onDismiss(id), SUCCESS_NOTICE_MS)
    return () => window.clearTimeout(timer)
  }, [success, id, onDismiss])

  return (
    <div
      role={success ? 'status' : 'alert'}
      className={success ? `${styles.notice} ${styles.success}` : styles.notice}
    >
      <p className={styles.title}>{notice.title}</p>
      {notice.detail ? <p>{notice.detail}</p> : null}
      {notice.reference ? <p className={styles.reference}>Reference: {notice.reference}</p> : null}
      <button type="button" className={styles.dismiss} onClick={() => onDismiss(id)}>
        Dismiss
      </button>
    </div>
  )
}

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notices, setNotices] = useState<Notice[]>([])
  const nextId = useRef(1)

  const notify = useCallback((notice: NoticeContent) => {
    const id = nextId.current
    nextId.current += 1
    setNotices((current) => [...current, { ...notice, id }])
  }, [])

  const dismiss = useCallback(
    (id: number) => setNotices((current) => current.filter((notice) => notice.id !== id)),
    [],
  )

  const api = useMemo(() => ({ notify }), [notify])

  return (
    <NotificationContext.Provider value={api}>
      {children}
      <section className={styles.region} aria-label="Notifications" aria-live="polite">
        {notices.map((notice) => (
          <NoticeItem key={notice.id} notice={notice} onDismiss={dismiss} />
        ))}
      </section>
    </NotificationContext.Provider>
  )
}

export function useNotify(): NotificationApi['notify'] {
  const api = useContext(NotificationContext)
  if (api === null) {
    throw new Error('useNotify must be used inside NotificationProvider.')
  }
  return api.notify
}

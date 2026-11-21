import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'

import type { NoticeContent } from './describeProblem'
import styles from './Notifications.module.css'

type Notice = NoticeContent & { id: number }

type NotificationApi = {
  notify: (notice: NoticeContent) => void
}

const NotificationContext = createContext<NotificationApi | null>(null)

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notices, setNotices] = useState<Notice[]>([])
  const nextId = useRef(1)

  const notify = useCallback((notice: NoticeContent) => {
    const id = nextId.current
    nextId.current += 1
    setNotices((current) => [...current, { ...notice, id }])
  }, [])

  const dismiss = (id: number) =>
    setNotices((current) => current.filter((notice) => notice.id !== id))

  const api = useMemo(() => ({ notify }), [notify])

  return (
    <NotificationContext.Provider value={api}>
      {children}
      <section className={styles.region} aria-label="Notifications" aria-live="polite">
        {notices.map((notice) => (
          <div key={notice.id} role="alert" className={styles.notice}>
            <p className={styles.title}>{notice.title}</p>
            {notice.detail ? <p>{notice.detail}</p> : null}
            {notice.reference ? (
              <p className={styles.reference}>Reference: {notice.reference}</p>
            ) : null}
            <button type="button" onClick={() => dismiss(notice.id)}>
              Dismiss
            </button>
          </div>
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

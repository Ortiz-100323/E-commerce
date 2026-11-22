import { useEffect, useState } from 'react'

import controls from '../styles/controls.module.css'
import styles from './AppShell.module.css'

export const VERSION_URL = '/version.json'
export const VERSION_CHECK_MS = 5 * 60 * 1000
export const DEV_BUILD = 'dev'

async function serverBuild(): Promise<string | null> {
  try {
    const response = await fetch(VERSION_URL, { cache: 'no-store' })
    if (!response.ok) {
      return null
    }
    const body: unknown = await response.json()
    if (typeof body === 'object' && body !== null && 'build' in body) {
      return typeof body.build === 'string' ? body.build : null
    }
    return null
  } catch {
    return null
  }
}

type NewVersionBannerProps = {
  currentBuild?: string
  everyMs?: number
  onReload?: () => void
}

export function NewVersionBanner({
  currentBuild = __APP_BUILD__,
  everyMs = VERSION_CHECK_MS,
  onReload = () => window.location.reload(),
}: NewVersionBannerProps) {
  const [available, setAvailable] = useState(false)

  useEffect(() => {
    if (currentBuild === DEV_BUILD || available) {
      return undefined
    }
    let active = true
    const check = async () => {
      const build = await serverBuild()
      if (active && build !== null && build !== currentBuild) {
        setAvailable(true)
      }
    }
    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        void check()
      }
    }
    const timer = window.setInterval(() => void check(), everyMs)
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      active = false
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [currentBuild, everyMs, available])

  if (!available) {
    return null
  }
  return (
    <div role="status" className={styles.newVersion}>
      <p>A new version of this site is available.</p>
      <button type="button" className={controls.primary} onClick={onReload}>
        Reload
      </button>
    </div>
  )
}

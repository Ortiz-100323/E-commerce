import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

import { readActor, writeActor } from './actorStorage'

type ActorApi = {
  actor: string | null
  setActor: (name: string) => void
}

const ActorContext = createContext<ActorApi | null>(null)

export function ActorProvider({ children }: { children: ReactNode }) {
  const [actor, setState] = useState<string | null>(() => readActor())

  const setActor = useCallback((name: string) => {
    writeActor(name)
    setState(name)
  }, [])

  const api = useMemo(() => ({ actor, setActor }), [actor, setActor])

  return <ActorContext.Provider value={api}>{children}</ActorContext.Provider>
}

export function useActor(): ActorApi {
  const api = useContext(ActorContext)
  if (api === null) {
    throw new Error('useActor must be used inside ActorProvider.')
  }
  return api
}

export function useRequiredActor(): string {
  const { actor } = useActor()
  if (actor === null) {
    throw new Error('A change needs a reviewer name; render it inside the admin area.')
  }
  return actor
}

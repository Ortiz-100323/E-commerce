export const ACTOR_STORAGE_KEY = 'ecommerce.actor'

let memory: string | null = null

export function readActor(): string | null {
  try {
    const stored = window.localStorage.getItem(ACTOR_STORAGE_KEY)
    if (stored !== null) {
      return stored
    }
  } catch {
    return memory
  }
  return memory
}

export function writeActor(name: string): void {
  memory = name
  try {
    window.localStorage.setItem(ACTOR_STORAGE_KEY, name)
  } catch {
    return
  }
}

export function forgetActorInMemory(): void {
  memory = null
}

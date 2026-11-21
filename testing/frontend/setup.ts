import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll, vi } from 'vitest'

import { forgetActorInMemory } from '../../frontend/src/actor/actorStorage'
import { server } from './support/server'

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' })
})

afterEach(() => {
  cleanup()
  server.resetHandlers()
  window.localStorage.clear()
  forgetActorInMemory()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

afterAll(() => {
  server.close()
})

import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll, beforeEach, expect, vi, type MockInstance } from 'vitest'

import { forgetActorInMemory } from '../../frontend/src/actor/actorStorage'
import {
  errorNotificationsOnPage,
  pageShowsUnexpectedError,
  takeErrorExpectation,
} from './support/pageGuard'
import { server } from './support/server'

let consoleError: MockInstance<typeof console.error>

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' })
})

beforeEach(() => {
  consoleError = vi.spyOn(console, 'error')
})

afterEach(() => {
  const unexpected = consoleError.mock.calls.filter((call) => call[0] === 'Unexpected error')
  const showedUnexpected = pageShowsUnexpectedError()
  const errorNotices = errorNotificationsOnPage()
  const errorsExpected = takeErrorExpectation()
  cleanup()
  server.resetHandlers()
  window.localStorage.clear()
  forgetActorInMemory()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  expect(unexpected, 'the app reported an unexpected error').toEqual([])
  expect(showedUnexpected, 'the page showed "Something unexpected went wrong"').toBe(false)
  if (!errorsExpected) {
    expect(errorNotices, 'error notifications the test did not expect').toEqual([])
  }
})

afterAll(() => {
  server.close()
})

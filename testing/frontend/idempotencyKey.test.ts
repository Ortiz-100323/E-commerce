import { afterEach, describe, expect, it, vi } from 'vitest'

import { newIdempotencyKey } from '../../frontend/src/api/idempotencyKey'

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('a new idempotency key', () => {
  it('uses the browser UUID generator when the page is a secure context', () => {
    const randomUUID = vi.fn(() => '6f1c2a00-0000-4000-8000-000000000001')
    vi.stubGlobal('crypto', { randomUUID, getRandomValues: crypto.getRandomValues.bind(crypto) })

    expect(newIdempotencyKey()).toBe('6f1c2a00-0000-4000-8000-000000000001')
    expect(randomUUID).toHaveBeenCalledOnce()
  })

  it('still makes a version 4 UUID over plain HTTP, where randomUUID does not exist', () => {
    vi.stubGlobal('crypto', { getRandomValues: crypto.getRandomValues.bind(crypto) })

    const keys = new Set(Array.from({ length: 200 }, () => newIdempotencyKey()))

    expect(keys.size).toBe(200)
    for (const key of keys) {
      expect(key).toMatch(UUID_V4)
    }
  })
})

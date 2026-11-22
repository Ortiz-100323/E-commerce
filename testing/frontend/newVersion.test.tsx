import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw/http'
import { describe, expect, it, vi } from 'vitest'

import { NewVersionBanner } from '../../frontend/src/app/NewVersionBanner'
import { server } from './support/server'

function serveBuild(respond: () => Response) {
  const calls: string[] = []
  server.use(
    http.get('*/version.json', ({ request }) => {
      calls.push(request.url)
      return respond()
    }),
  )
  return calls
}

async function wait(ms: number) {
  await new Promise((resolve) => setTimeout(resolve, ms))
}

describe('the new version banner', () => {
  it('offers a reload when the server runs a newer build', async () => {
    serveBuild(() => HttpResponse.json({ build: 'build-2' }))
    const reload = vi.fn()
    render(<NewVersionBanner currentBuild="build-1" everyMs={20} onReload={reload} />)

    expect(await screen.findByText('A new version of this site is available.')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: 'Reload' }))
    expect(reload).toHaveBeenCalledOnce()
  })

  it('stays hidden while the build is the same', async () => {
    const calls = serveBuild(() => HttpResponse.json({ build: 'build-1' }))
    render(<NewVersionBanner currentBuild="build-1" everyMs={20} onReload={vi.fn()} />)

    await wait(120)

    expect(calls.length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: 'Reload' })).not.toBeInTheDocument()
  })

  it('ignores a failed or odd answer and keeps quiet', async () => {
    let answer = 0
    serveBuild(() => {
      answer += 1
      return answer % 2 === 0
        ? new HttpResponse('<html></html>', { headers: { 'Content-Type': 'text/html' } })
        : new HttpResponse(null, { status: 503 })
    })
    render(<NewVersionBanner currentBuild="build-1" everyMs={20} onReload={vi.fn()} />)

    await wait(150)

    expect(answer).toBeGreaterThan(1)
    expect(screen.queryByRole('button', { name: 'Reload' })).not.toBeInTheDocument()
  })

  it('checks again when the tab becomes visible', async () => {
    const calls = serveBuild(() => HttpResponse.json({ build: 'build-2' }))
    render(<NewVersionBanner currentBuild="build-1" everyMs={60_000} onReload={vi.fn()} />)

    document.dispatchEvent(new Event('visibilitychange'))

    expect(await screen.findByRole('button', { name: 'Reload' })).toBeVisible()
    expect(calls).toHaveLength(1)
  })

  it('never checks in development', async () => {
    const calls = serveBuild(() => HttpResponse.json({ build: 'build-2' }))
    render(<NewVersionBanner currentBuild="dev" everyMs={20} onReload={vi.fn()} />)

    await wait(80)
    document.dispatchEvent(new Event('visibilitychange'))

    expect(calls).toHaveLength(0)
  })
})

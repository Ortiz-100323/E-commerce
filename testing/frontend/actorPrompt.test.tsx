import { useMutation } from '@tanstack/react-query'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw/http'
import { describe, expect, it, vi } from 'vitest'

import { ACTOR_STORAGE_KEY } from '../../frontend/src/actor/actorStorage'
import { useRequiredActor } from '../../frontend/src/actor/ActorContext'
import { productsApi } from '../../frontend/src/api/products'
import { AppShell } from '../../frontend/src/app/AppShell'
import { AdminLayout } from '../../frontend/src/features/admin/AdminLayout'
import { API, PRODUCT_ID, product } from './support/api'
import { renderApp } from './support/renderApp'
import { server } from './support/server'

function ChangeProbe() {
  const actor = useRequiredActor()
  const archive = useMutation({ mutationFn: () => productsApi.archive(PRODUCT_ID, actor) })
  const restore = useMutation({ mutationFn: () => productsApi.restore(PRODUCT_ID, actor) })
  return (
    <div>
      <button type="button" onClick={() => archive.mutate()}>
        Archive
      </button>
      <button type="button" onClick={() => restore.mutate()}>
        Restore
      </button>
      {archive.isSuccess || restore.isSuccess ? <p>Done</p> : null}
    </div>
  )
}

const probeRoutes = [
  {
    element: <AppShell />,
    children: [
      {
        path: 'admin',
        element: <AdminLayout />,
        children: [{ path: 'probe', element: <ChangeProbe /> }],
      },
    ],
  },
]

async function answerPrompt(name: string) {
  const dialog = await screen.findByRole('dialog', { name: 'Who is reviewing?' })
  const input = within(dialog).getByLabelText('Your name')
  await userEvent.clear(input)
  if (name) {
    await userEvent.click(input)
    await userEvent.paste(name)
  }
  await userEvent.click(within(dialog).getByRole('button', { name: 'Continue' }))
  return dialog
}

describe('who is reviewing', () => {
  it('asks for the name on the first visit to the admin area and remembers it', async () => {
    const first = renderApp('/admin/products')

    await answerPrompt('  Maria  ')

    expect(await screen.findByText('Maria')).toBeInTheDocument()
    expect(screen.getByText(/Reviewing as/)).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(window.localStorage.getItem(ACTOR_STORAGE_KEY)).toBe('Maria')
    first.unmount()

    renderApp('/admin/products')

    expect(await screen.findByRole('heading', { name: 'Products' })).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('does not show the admin content until a name is given', async () => {
    renderApp('/admin/products')

    await screen.findByRole('dialog', { name: 'Who is reviewing?' })

    expect(screen.queryByRole('heading', { name: 'Products' })).not.toBeInTheDocument()
  })

  it.each([
    ['', 'Tell us who is making this change.'],
    ['   ', 'Tell us who is making this change.'],
    ['x'.repeat(101), 'The name must be at most 100 characters.'],
    ['Ann\tSmith', 'The name must not contain line breaks, tabs or other control characters.'],
  ])('refuses the name %j with a clear message', async (name, message) => {
    renderApp('/admin/products')

    const dialog = await answerPrompt(name)

    expect(await within(dialog).findByText(message)).toBeInTheDocument()
    expect(within(dialog).getByLabelText('Your name')).toHaveAttribute('aria-invalid', 'true')
    expect(window.localStorage.getItem(ACTOR_STORAGE_KEY)).toBeNull()
  })

  it('lets the reviewer change the name, or cancel', async () => {
    window.localStorage.setItem(ACTOR_STORAGE_KEY, 'Maria')
    renderApp('/admin/products')

    await userEvent.click(await screen.findByRole('button', { name: 'Change' }))
    const dialog = screen.getByRole('dialog', { name: 'Who is reviewing?' })
    expect(within(dialog).getByLabelText('Your name')).toHaveValue('Maria')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(screen.getByText('Maria')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Change' }))
    await answerPrompt('Antonio')

    expect(await screen.findByText('Antonio')).toBeInTheDocument()
    expect(window.localStorage.getItem(ACTOR_STORAGE_KEY)).toBe('Antonio')
  })

  it('sends the name on every change request, encoded for any alphabet', async () => {
    const seen: (string | null)[] = []
    const record = ({ request }: { request: Request }) => {
      seen.push(request.headers.get('X-Actor-Name'))
      return HttpResponse.json(product)
    }
    server.use(
      http.delete(`${API}/products/:id`, record),
      http.post(`${API}/products/:id/restore`, record),
    )
    renderApp('/admin/probe', { routes: probeRoutes })
    await answerPrompt('Łukasz')

    await userEvent.click(await screen.findByRole('button', { name: 'Archive' }))
    await screen.findByText('Done')
    await userEvent.click(screen.getByRole('button', { name: 'Restore' }))

    await vi.waitFor(() => expect(seen).toHaveLength(2))
    expect(seen).toEqual(['%C5%81ukasz', '%C5%81ukasz'])
    expect(seen.map((value) => decodeURIComponent(value ?? ''))).toEqual(['Łukasz', 'Łukasz'])
  })

  it('still works for the session when the browser blocks storage', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('storage is blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('storage is blocked')
    })
    const first = renderApp('/admin/products')

    await answerPrompt('Maria')

    expect(await screen.findByText('Maria')).toBeInTheDocument()
    first.unmount()
    renderApp('/admin/products')
    expect(await screen.findByText('Maria')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

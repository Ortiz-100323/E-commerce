import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { ACTOR_STORAGE_KEY } from '../../frontend/src/actor/actorStorage'
import { renderApp } from './support/renderApp'

function signIn(name = 'Maria') {
  window.localStorage.setItem(ACTOR_STORAGE_KEY, name)
}

describe('the app shell', () => {
  it('shows the shop at the root, inside the shell', async () => {
    renderApp('/')

    expect(await screen.findByRole('heading', { name: 'Shop' })).toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(within(nav).getByRole('link', { name: 'Shop' })).toHaveAttribute('aria-current', 'page')
    expect(within(nav).getByRole('link', { name: 'Admin' })).toBeInTheDocument()
  })

  it('shows the admin products page inside the shell', async () => {
    signIn()
    renderApp('/admin/products')

    expect(await screen.findByRole('heading', { name: 'Admin' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Products' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument()
  })

  it('sends /admin to the products page', async () => {
    signIn()
    const { router } = renderApp('/admin')

    expect(await screen.findByRole('heading', { name: 'Products' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/admin/products')
  })

  it('moves between the areas with the header links', async () => {
    signIn()
    renderApp('/')

    await userEvent.click(screen.getByRole('link', { name: 'Admin' }))
    expect(await screen.findByRole('heading', { name: 'Products' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('link', { name: 'Shop' }))
    expect(await screen.findByRole('heading', { name: 'Shop' })).toBeInTheDocument()
  })

  it('shows "Page not found" for an unknown address, inside the shell', async () => {
    renderApp('/no/such/page')

    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Go to the shop' })).toHaveAttribute('href', '/')
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument()
  })

  it('never asks for a name in the shop', async () => {
    renderApp('/')

    await screen.findByRole('heading', { name: 'Shop' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

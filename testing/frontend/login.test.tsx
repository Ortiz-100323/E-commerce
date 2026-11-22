import { screen, waitFor, within } from '@testing-library/react'
import userEvent, { type UserEvent } from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import { fakeCatalog } from './support/fakeCatalog'
import { endFakeSession, fakeAccounts, logInAs, TEST_PASSWORD } from './support/fakeSession'
import { renderApp } from './support/renderApp'

let user: UserEvent

beforeEach(() => {
  user = userEvent.setup()
})

function header() {
  return within(screen.getByRole('banner'))
}

async function logIn(email: string, password = TEST_PASSWORD) {
  const form = within(await screen.findByRole('region', { name: 'I have an account' }))
  await user.type(form.getByLabelText('Email'), email)
  await user.type(form.getByLabelText('Password'), password)
  await user.click(form.getByRole('button', { name: 'Log in' }))
}

describe('one Log in button for everyone', () => {
  it('shows Log in to a visitor, and no Admin link', async () => {
    renderApp('/')

    const login = await header().findByRole('link', { name: 'Log in' })
    expect(login).toHaveAttribute('href', '/login?next=%2F')
    expect(header().queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument()
  })

  it('sends an admin to the admin area after logging in', async () => {
    fakeCatalog([{ sku: 'RS-001', name: 'Running Shoes' }])
    const { router } = renderApp('/login')

    await logIn('maria@example.com')

    await waitFor(() => expect(router.state.location.pathname).toBe('/admin/products'))
    expect(await header().findByRole('link', { name: 'Admin' })).toBeInTheDocument()
    expect(header().getByText('Maria')).toBeInTheDocument()
    expect(header().getByRole('button', { name: 'Log out' })).toBeInTheDocument()
  })

  it('sends a buyer back to the shop page they came from', async () => {
    fakeCatalog([{ sku: 'RS-001', name: 'Running Shoes' }])
    const { router } = renderApp('/login?next=%2Fcart')

    await logIn('bea@example.com')

    await waitFor(() => expect(router.state.location.pathname).toBe('/cart'))
    expect(await header().findByRole('link', { name: 'My orders' })).toBeInTheDocument()
    expect(header().queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument()
  })

  it('says the same thing for a wrong email or a wrong password', async () => {
    const { router } = renderApp('/login')

    await logIn('maria@example.com', 'a wrong password')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The email or password is incorrect.',
    )
    await user.clear(screen.getAllByLabelText('Email')[0])
    await user.clear(screen.getAllByLabelText('Password')[0])
    await logIn('nobody@example.com')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The email or password is incorrect.',
    )
    expect(router.state.location.pathname).toBe('/login')
  })

  it('tells how long to wait after too many attempts', async () => {
    renderApp('/login')

    for (let attempt = 0; attempt < 6; attempt += 1) {
      await logIn('maria@example.com', 'a wrong password')
      await screen.findByRole('alert')
      await user.clear(screen.getAllByLabelText('Email')[0])
      await user.clear(screen.getAllByLabelText('Password')[0])
    }

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Too many attempts. Try again in 10 minutes.',
    )
  })

  it('never follows a next address to another site', async () => {
    fakeCatalog([])
    const { router } = renderApp('/login?next=https%3A%2F%2Fevil.example%2F')

    await logIn('maria@example.com')

    await waitFor(() => expect(router.state.location.pathname).toBe('/admin/products'))
  })

  it('logs out and shows Log in again', async () => {
    logInAs('ADMIN')
    const { router } = renderApp('/admin/products')

    await user.click(await header().findByRole('button', { name: 'Log out' }))

    expect(await header().findByRole('link', { name: 'Log in' })).toBeInTheDocument()
    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
  })
})

describe('the admin area is for admins only', () => {
  it('asks a visitor to log in, then returns to the page they asked for', async () => {
    fakeCatalog([{ sku: 'RS-001', name: 'Running Shoes' }])
    const { router } = renderApp('/admin/imports/new')

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(router.state.location.search).toBe('?next=%2Fadmin%2Fimports%2Fnew')
    await logIn('maria@example.com')

    await waitFor(() => expect(router.state.location.pathname).toBe('/admin/imports/new'))
  })

  it('blocks a buyer without asking the server for any admin data', async () => {
    const catalog = fakeCatalog([{ sku: 'RS-001', name: 'Running Shoes' }])
    logInAs('BUYER')
    renderApp('/admin/products')

    expect(
      await screen.findByRole('heading', { name: 'This area is for administrators' }),
    ).toBeVisible()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(catalog.lists).toEqual([])
    expect(header().queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument()
  })

  it('never lets a logged-in buyer reach the admin area through the login page', async () => {
    logInAs('BUYER')
    const { router } = renderApp('/login?next=%2Fadmin%2Fproducts')

    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
  })

  it('returns to the login when the session ends during work, without an error pop-up', async () => {
    fakeCatalog([{ sku: 'RS-001', name: 'Running Shoes' }])
    logInAs('ADMIN')
    const { router } = renderApp('/admin/products')
    const history = await screen.findByRole('link', { name: 'History' })

    endFakeSession()
    await user.click(history)

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(await screen.findByText('Your session ended. Log in again.')).toBeVisible()
    expect(screen.queryByRole('region', { name: 'Notifications' })).not.toHaveTextContent(
      /unexpected/i,
    )
  })
})

describe('admins create admins', () => {
  it('lists the admins and creates a new one', async () => {
    logInAs('ADMIN')
    renderApp('/admin/accounts')

    const table = await screen.findByRole('table', { name: 'Administrators' })
    expect(within(table).getByText('maria@example.com')).toBeInTheDocument()
    const form = within(screen.getByRole('region', { name: 'Create admin' }))
    await user.type(form.getByLabelText('Name'), 'Ana Souza')
    await user.type(form.getByLabelText('Email'), 'ana@example.com')
    await user.type(form.getByLabelText('Password'), 'another long password')
    await user.click(form.getByRole('button', { name: 'Create admin' }))

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Ana Souza can now log in as an administrator with ana@example.com.',
    )
    expect(fakeAccounts().find((account) => account.email === 'ana@example.com')?.role).toBe(
      'ADMIN',
    )
    expect(await within(table).findByText('ana@example.com')).toBeInTheDocument()
  })

  it('refuses an email that already has an account, and keeps that account as it is', async () => {
    logInAs('ADMIN')
    renderApp('/admin/accounts')
    const form = within(await screen.findByRole('region', { name: 'Create admin' }))

    await user.type(form.getByLabelText('Name'), 'Bea')
    await user.type(form.getByLabelText('Email'), 'bea@example.com')
    await user.type(form.getByLabelText('Password'), 'another long password')
    await user.click(form.getByRole('button', { name: 'Create admin' }))

    expect(
      await form.findByText(
        'An account with this email already exists. Each email can have only one account.',
      ),
    ).toBeVisible()
    expect(fakeAccounts().find((account) => account.email === 'bea@example.com')?.role).toBe(
      'BUYER',
    )
  })

  it('checks the details before sending anything', async () => {
    logInAs('ADMIN')
    renderApp('/admin/accounts')
    const form = within(await screen.findByRole('region', { name: 'Create admin' }))

    await user.type(form.getByLabelText('Email'), 'not an email')
    await user.type(form.getByLabelText('Password'), 'short')
    await user.click(form.getByRole('button', { name: 'Create admin' }))

    expect(await form.findByText('Enter your name.')).toBeVisible()
    expect(form.getByText('Enter an email address like name@example.com.')).toBeVisible()
    expect(form.getByText('Use at least 12 characters.')).toBeVisible()
  })
})

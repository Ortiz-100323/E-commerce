import { screen, waitFor, within } from '@testing-library/react'
import userEvent, { type UserEvent } from '@testing-library/user-event'
import { http } from 'msw/http'
import { beforeEach, describe, expect, it } from 'vitest'

import type { Order } from '../../frontend/src/api/orders'
import { CART_STORAGE_KEY } from '../../frontend/src/cart/cart'
import { API, problem } from './support/api'
import { fakeCatalog } from './support/fakeCatalog'
import { fakeOrders } from './support/fakeOrders'
import { fakeAccounts, fakeSessionRequests, logInAs, setMyOrders } from './support/fakeSession'
import { renderApp } from './support/renderApp'
import { server } from './support/server'

let user: UserEvent

beforeEach(() => {
  user = userEvent.setup()
})

function header() {
  return within(screen.getByRole('banner'))
}

async function signUpForm() {
  return within(await screen.findByRole('region', { name: 'New here? Create an account' }))
}

function order(id: string, created: string, total: string): Order {
  return {
    id,
    status: 'PAID',
    customer: { name: 'Bea', email: 'bea@example.com' },
    lines: [
      {
        sku: 'RS-001',
        product_id: 'p-1',
        name: 'Running Shoes',
        unit_price: total,
        quantity: 1,
        gift: false,
        line_total: total,
      },
    ],
    total,
    currency: 'USD',
    card_last4: '4242',
    payment_reference: 'pay-1',
    decline_reason: null,
    created_at: created,
    settled_at: created,
  }
}

describe('signing up on the login page', () => {
  it('creates a customer account, logs in and goes back to the shop', async () => {
    fakeCatalog([])
    const { router } = renderApp('/login?next=%2F')
    const form = await signUpForm()

    await user.type(form.getByLabelText('Name'), 'Carla Dias')
    await user.type(form.getByLabelText('Email'), 'carla@example.com')
    await user.type(form.getByLabelText('Password'), 'a long password here')
    await user.click(form.getByRole('button', { name: 'Create account' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
    expect(await header().findByRole('link', { name: 'My orders' })).toBeInTheDocument()
    expect(fakeAccounts().find((account) => account.email === 'carla@example.com')?.role).toBe(
      'BUYER',
    )
  })

  it('sends only a name, an email and a password, never a role', async () => {
    fakeCatalog([])
    renderApp('/login')
    const form = await signUpForm()

    await user.type(form.getByLabelText('Name'), 'Carla')
    await user.type(form.getByLabelText('Email'), 'carla@example.com')
    await user.type(form.getByLabelText('Password'), 'a long password here')
    await user.click(form.getByRole('button', { name: 'Create account' }))

    await waitFor(() => expect(fakeSessionRequests()).toHaveLength(1))
    expect(Object.keys(fakeSessionRequests()[0].body as object).sort()).toEqual([
      'email',
      'name',
      'password',
    ])
  })

  it('says when the email already has an account', async () => {
    renderApp('/login')
    const form = await signUpForm()

    await user.type(form.getByLabelText('Name'), 'Maria')
    await user.type(form.getByLabelText('Email'), 'maria@example.com')
    await user.type(form.getByLabelText('Password'), 'a long password here')
    await user.click(form.getByRole('button', { name: 'Create account' }))

    expect(
      await form.findByText('An account with this email already exists. Log in instead.'),
    ).toBeVisible()
    expect(fakeAccounts().find((account) => account.email === 'maria@example.com')?.role).toBe(
      'ADMIN',
    )
  })

  it('a new customer still cannot open the admin area', async () => {
    fakeCatalog([])
    const { router } = renderApp('/login')
    const form = await signUpForm()
    await user.type(form.getByLabelText('Name'), 'Carla')
    await user.type(form.getByLabelText('Email'), 'carla@example.com')
    await user.type(form.getByLabelText('Password'), 'a long password here')
    await user.click(form.getByRole('button', { name: 'Create account' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/'))

    await router.navigate('/admin/products')

    expect(
      await screen.findByRole('heading', { name: 'This area is for administrators' }),
    ).toBeVisible()
  })
})

describe('My orders', () => {
  it('lists the customer’s orders, newest first, with a link to each', async () => {
    logInAs('BUYER')
    setMyOrders([
      order('bbbbbbbb-0000-4000-8000-000000000002', '2026-11-22T10:00:00Z', '25.00'),
      order('aaaaaaaa-0000-4000-8000-000000000001', '2026-11-21T10:00:00Z', '89.99'),
    ])
    renderApp('/account/orders')

    const list = await screen.findByRole('list', { name: 'Orders' })
    const rows = within(list).getAllByRole('listitem')
    expect(rows.map((row) => row.getAttribute('aria-label'))).toEqual([
      'Order BBBBBBBB',
      'Order AAAAAAAA',
    ])
    expect(within(rows[0]).getByText('$25.00')).toBeVisible()
    expect(within(rows[0]).getByRole('link', { name: 'Order BBBBBBBB' })).toHaveAttribute(
      'href',
      '/orders/bbbbbbbb-0000-4000-8000-000000000002',
    )
  })

  it('invites a customer without orders to start shopping', async () => {
    logInAs('BUYER')
    renderApp('/account/orders')

    expect(await screen.findByText('No orders yet')).toBeVisible()
    expect(screen.getByRole('link', { name: 'Start shopping' })).toHaveAttribute('href', '/')
  })

  it('pages through many orders', async () => {
    logInAs('BUYER')
    setMyOrders(
      Array.from({ length: 12 }, (_, index) =>
        order(
          `${String(index).padStart(8, '0')}-0000-4000-8000-000000000000`,
          '2026-11-22T10:00:00Z',
          '1.00',
        ),
      ),
    )
    renderApp('/account/orders')

    expect(await screen.findByText('Page 1 of 2')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Page 2 of 2')).toBeVisible()
  })

  it('tells an admin that My orders is for customers', async () => {
    logInAs('ADMIN')
    renderApp('/account/orders')

    expect(
      await screen.findByRole('heading', { name: 'My orders is for customer accounts' }),
    ).toBeVisible()
  })

  it('asks a visitor to log in first', async () => {
    const { router } = renderApp('/account/orders')

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(router.state.location.search).toBe('?next=%2Faccount%2Forders')
  })
})

describe('checkout with an account', () => {
  const SHOES = { sku: 'RS-001', name: 'Running Shoes', price: '89.99', stock: 10 }

  function seedCart() {
    window.localStorage.setItem(
      CART_STORAGE_KEY,
      JSON.stringify([
        {
          productId: 'product-RS-001',
          sku: 'RS-001',
          name: 'Running Shoes',
          price: '89.99',
          quantity: 1,
        },
      ]),
    )
  }

  it('fills in the customer’s name and email and says the order is kept', async () => {
    fakeOrders([SHOES])
    seedCart()
    logInAs('BUYER')
    renderApp('/checkout')

    expect(await screen.findByLabelText('Name')).toHaveValue('Bea')
    expect(screen.getByLabelText('Email')).toHaveValue('bea@example.com')
    expect(screen.getByText('This order will be kept in My orders.')).toBeVisible()
  })

  it('offers a visitor to log in, and lets them pay as a guest', async () => {
    fakeOrders([SHOES])
    seedCart()
    renderApp('/checkout')

    const hint = await screen.findByText(/or simply pay as a guest/)
    expect(within(hint).getByRole('link', { name: 'Log in' })).toHaveAttribute(
      'href',
      '/login?next=%2Fcheckout',
    )
    expect(screen.getByLabelText('Name')).toHaveValue('')
  })

  it('explains a login that ended while paying, and charges nothing', async () => {
    fakeOrders([SHOES])
    seedCart()
    logInAs('BUYER')
    server.use(
      http.post(`${API}/orders`, () =>
        problem({ status: 401, slug: 'authentication-required', title: 'Log in to continue.' }),
      ),
    )
    renderApp('/checkout')
    await screen.findByLabelText('Name')
    await user.type(screen.getByLabelText('Card number'), '4242 4242 4242 4242')
    await user.type(screen.getByLabelText('Expiry (MM/YY)'), '12/30')
    await user.type(screen.getByLabelText('CVC'), '123')

    await user.click(screen.getByRole('button', { name: /^Pay / }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Your login ended, so nothing was charged.',
    )
    expect(header().getByRole('link', { name: 'Log in' })).toBeInTheDocument()
  })
})

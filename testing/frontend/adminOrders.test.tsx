import { screen, waitFor, within } from '@testing-library/react'
import userEvent, { type UserEvent } from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import { CART_STORAGE_KEY } from '../../frontend/src/cart/cart'
import { adminOrder, fakeAdminOrders } from './support/fakeAdminOrders'
import { fakeCatalog } from './support/fakeCatalog'
import { logInAs } from './support/fakeSession'
import { renderApp } from './support/renderApp'

let user: UserEvent

beforeEach(() => {
  user = userEvent.setup()
})

function header() {
  return within(screen.getByRole('banner'))
}

describe('admins do not shop', () => {
  it('shows an admin the products without Add to cart, and no Cart in the header', async () => {
    fakeCatalog([{ sku: 'RS-001', name: 'Running Shoes', price: '89.99', stock: 5 }])
    logInAs('ADMIN')
    renderApp('/')

    const card = within(await screen.findByRole('listitem', { name: 'Running Shoes' }))
    expect(card.getByText('$89.99')).toBeVisible()
    await header().findByRole('link', { name: 'Admin' })
    expect(card.queryByRole('button', { name: 'Add to cart' })).not.toBeInTheDocument()
    expect(header().queryByRole('link', { name: /^Cart: / })).not.toBeInTheDocument()
  })

  it('tells an admin on a product page that admins can’t buy', async () => {
    const catalog = fakeCatalog([{ sku: 'RS-001', name: 'Running Shoes', stock: 5 }])
    logInAs('ADMIN')
    renderApp(`/products/${catalog.bySku('RS-001')?.id}`)

    expect(
      await screen.findByText("You're logged in as an administrator, so you can't buy here."),
    ).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Add to cart' })).not.toBeInTheDocument()
  })

  it.each(['/cart', '/checkout'])('blocks %s for an admin and keeps the cart', async (path) => {
    const cart = [
      { productId: 'p', sku: 'RS-001', name: 'Running Shoes', price: '1.00', quantity: 1 },
    ]
    window.localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(cart))
    logInAs('ADMIN')
    renderApp(path)

    expect(
      await screen.findByRole('heading', { name: "Administrator accounts can't place orders" }),
    ).toBeVisible()
    expect(screen.getByRole('link', { name: 'See all orders' })).toHaveAttribute(
      'href',
      '/admin/orders',
    )
    expect(JSON.parse(window.localStorage.getItem(CART_STORAGE_KEY) ?? '[]')).toEqual(cart)
  })

  it('still lets customers and visitors add to the cart', async () => {
    fakeCatalog([{ sku: 'RS-001', name: 'Running Shoes', stock: 5 }])
    logInAs('BUYER')
    renderApp('/')

    const card = within(await screen.findByRole('listitem', { name: 'Running Shoes' }))
    expect(card.getByRole('button', { name: 'Add to cart' })).toBeEnabled()
    expect(await header().findByRole('link', { name: /^Cart: / })).toBeInTheDocument()
  })
})

describe('the admin Orders screen', () => {
  const ORDERS = [
    adminOrder(1, { name: 'Ana Souza', email: 'ana@example.com' }),
    adminOrder(2, { name: 'Carla Dias', email: 'carla@example.com', customer_account: true }),
    adminOrder(3, {
      name: 'Bruno Lima',
      email: 'bruno@example.com',
      status: 'PAYMENT_FAILED',
      decline_reason: 'card_declined',
      card_last4: '0002',
    }),
  ]

  it('lists every order with the customer, guest or account, total and status', async () => {
    fakeAdminOrders(ORDERS)
    logInAs('ADMIN')
    renderApp('/admin/orders')

    const table = within(await screen.findByRole('table', { name: 'Orders' }))
    const carla = within(table.getByRole('row', { name: 'Order 00000002' }))
    expect(carla.getByText('Carla Dias')).toBeVisible()
    expect(carla.getByText('carla@example.com')).toBeVisible()
    expect(carla.getByText('Customer account')).toBeVisible()
    expect(carla.getByText('$179.98')).toBeVisible()
    expect(
      within(table.getByRole('row', { name: 'Order 00000001' })).getByText('Guest'),
    ).toBeVisible()
    expect(
      within(table.getByRole('row', { name: 'Order 00000003' })).getByText('Payment declined'),
    ).toBeVisible()
    expect(screen.getByText('3 orders')).toBeVisible()
  })

  it('searches by customer and filters by status', async () => {
    const fake = fakeAdminOrders(ORDERS)
    logInAs('ADMIN')
    const { router } = renderApp('/admin/orders')
    await screen.findByRole('table', { name: 'Orders' })

    await user.type(screen.getByRole('searchbox', { name: 'Search' }), 'carla')
    await user.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => expect(screen.getAllByRole('row')).toHaveLength(2))
    expect(router.state.location.search).toBe('?q=carla')

    await user.selectOptions(screen.getByRole('combobox', { name: 'Status' }), 'PAYMENT_FAILED')
    expect(await screen.findByText('No orders match.')).toBeVisible()
    expect(fake.queries.at(-1)).toMatchObject({ q: 'carla', status: 'PAYMENT_FAILED' })

    await user.click(screen.getByRole('link', { name: 'Clear filters' }))
    await waitFor(() => expect(screen.getAllByRole('row')).toHaveLength(4))
  })

  it('pages through many orders', async () => {
    fakeAdminOrders(Array.from({ length: 23 }, (_, index) => adminOrder(index + 1)))
    logInAs('ADMIN')
    renderApp('/admin/orders')

    expect(await screen.findByText('Page 1 of 2')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Page 2 of 2')).toBeVisible()
  })

  it('opens an order in full from its row', async () => {
    fakeAdminOrders(ORDERS)
    logInAs('ADMIN')
    const { router } = renderApp('/admin/orders')
    const row = await screen.findByRole('row', { name: 'Order 00000003' })

    await user.click(within(row).getByText('Bruno Lima'))

    await waitFor(() =>
      expect(router.state.location.pathname).toBe(`/admin/orders/${ORDERS[2].id}`),
    )
    expect(await screen.findByRole('heading', { name: 'Order 00000003' })).toBeVisible()
    expect(screen.getByText(/ending in 0002 was declined \(card_declined\)/)).toBeVisible()
    expect(screen.getByRole('cell', { name: 'Running Shoes RS-001' })).toBeVisible()
  })

  it('says when an order does not exist', async () => {
    fakeAdminOrders(ORDERS)
    logInAs('ADMIN')
    renderApp('/admin/orders/99999999-0000-4000-8000-000000000000')

    expect(await screen.findByRole('heading', { name: 'Order not found' })).toBeVisible()
  })

  it('invites patience when there are no orders yet', async () => {
    fakeAdminOrders([])
    logInAs('ADMIN')
    renderApp('/admin/orders')

    expect(await screen.findByText('Orders appear here as soon as customers buy.')).toBeVisible()
  })

  it('is closed to customers', async () => {
    fakeAdminOrders(ORDERS)
    logInAs('BUYER')
    renderApp('/admin/orders')

    expect(
      await screen.findByRole('heading', { name: 'This area is for administrators' }),
    ).toBeVisible()
  })
})

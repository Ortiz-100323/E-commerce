import { screen, waitFor, within } from '@testing-library/react'
import userEvent, { type UserEvent } from '@testing-library/user-event'
import { HttpResponse } from 'msw/http'
import { beforeEach, describe, expect, it } from 'vitest'

import { CART_STORAGE_KEY, type CartLine } from '../../frontend/src/cart/cart'
import { problem, validationProblem } from './support/api'
import { fakeOrders, type ShopItem } from './support/fakeOrders'
import { renderApp } from './support/renderApp'

const SHOES: ShopItem = { sku: 'RS-001', name: 'Running Shoes', price: '89.99', stock: 10 }
const MAT: ShopItem = { sku: 'YM-015', name: 'Yoga Mat', price: '25.00', stock: 3 }
const GIFT: ShopItem = { sku: 'GF-002', name: 'Collar gift', price: '0.00', stock: 20 }
const TENT: ShopItem = { sku: 'CT-005', name: 'Camping Tent', price: '199.99', stock: 0 }
const OLD: ShopItem = { sku: 'OLD-1', name: 'Old Shoes', price: '10.00', stock: 5, active: false }

let user: UserEvent

beforeEach(() => {
  user = userEvent.setup()
})

function cartLine(item: ShopItem, quantity: number, price = '1.00'): CartLine {
  return { productId: `product-${item.sku}`, sku: item.sku, name: item.name, price, quantity }
}

function seedCart(...lines: CartLine[]) {
  window.localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(lines))
}

function storedCart(): CartLine[] {
  return JSON.parse(window.localStorage.getItem(CART_STORAGE_KEY) ?? '[]') as CartLine[]
}

async function fillCustomer(name = 'Ana Souza', email = 'ana@example.com') {
  await user.type(await screen.findByLabelText('Name'), name)
  await user.type(screen.getByLabelText('Email'), email)
}

async function fillCard(number = '4242 4242 4242 4242', expiry = '12/30', cvc = '123') {
  await user.clear(screen.getByLabelText('Card number'))
  await user.type(screen.getByLabelText('Card number'), number)
  await user.clear(screen.getByLabelText('Expiry (MM/YY)'))
  await user.type(screen.getByLabelText('Expiry (MM/YY)'), expiry)
  await user.clear(screen.getByLabelText('CVC'))
  await user.type(screen.getByLabelText('CVC'), cvc)
}

function payButton() {
  return screen.getByRole('button', { name: /^Pay / })
}

describe('the cart', () => {
  it('opens from the header and shows prices and the subtotal from the server', async () => {
    const fake = fakeOrders([SHOES, MAT])
    seedCart(cartLine(SHOES, 2), cartLine(MAT, 1))
    renderApp('/')

    await user.click(screen.getByRole('link', { name: 'Cart: 3 items' }))

    expect(await screen.findByRole('heading', { name: 'Your cart' })).toBeVisible()
    const shoes = within(await screen.findByRole('listitem', { name: 'Running Shoes' }))
    expect(shoes.getByText('$89.99')).toBeVisible()
    expect(shoes.getByText('$179.98')).toBeVisible()
    expect(await screen.findByText('Subtotal: $204.98')).toBeVisible()
    expect(fake.quotes.at(-1)).toEqual([
      { sku: 'RS-001', quantity: 2 },
      { sku: 'YM-015', quantity: 1 },
    ])
    expect(screen.getByRole('button', { name: 'Go to checkout' })).toBeEnabled()
  })

  it('changes a quantity and removes a line, asking the server again each time', async () => {
    fakeOrders([SHOES, MAT])
    seedCart(cartLine(SHOES, 1), cartLine(MAT, 1))
    renderApp('/cart')

    const quantity = await screen.findByLabelText('Quantity of Running Shoes')
    await user.clear(quantity)
    await user.type(quantity, '3')
    expect(await screen.findByText('Subtotal: $294.97')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Remove Yoga Mat' }))

    expect(await screen.findByText('Subtotal: $269.97')).toBeVisible()
    expect(screen.queryByRole('listitem', { name: 'Yoga Mat' })).toBeNull()
    expect(storedCart().map((line) => [line.sku, line.quantity])).toEqual([['RS-001', 3]])
    expect(screen.getByRole('link', { name: 'Cart: 3 items' })).toBeVisible()
  })

  it('does not check out with an invalid quantity still visible in the cart', async () => {
    fakeOrders([SHOES])
    seedCart(cartLine(SHOES, 1))
    const { router } = renderApp('/cart')
    const quantity = await screen.findByLabelText('Quantity of Running Shoes')

    await user.clear(quantity)
    await user.type(quantity, '0')
    await user.click(screen.getByRole('button', { name: 'Go to checkout' }))

    expect(quantity).toBeInvalid()
    expect(router.state.location.pathname).toBe('/cart')
    expect(storedCart()[0].quantity).toBe(1)
  })

  it('offers a fix for every line the shop can no longer sell as asked', async () => {
    fakeOrders([SHOES, MAT, TENT, OLD])
    seedCart(cartLine(SHOES, 1), cartLine(MAT, 5), cartLine(TENT, 1), cartLine(OLD, 1))
    renderApp('/cart')

    const mat = within(await screen.findByRole('listitem', { name: 'Yoga Mat' }))
    expect(await mat.findByText('Only 3 left.')).toBeVisible()
    expect(
      within(screen.getByRole('listitem', { name: 'Camping Tent' })).getByText('Out of stock.'),
    ).toBeVisible()
    expect(
      within(screen.getByRole('listitem', { name: 'Old Shoes' })).getByText('No longer sold.'),
    ).toBeVisible()
    expect(screen.getByRole('button', { name: 'Go to checkout' })).toBeDisabled()

    await user.click(mat.getByRole('button', { name: 'Use 3' }))
    await user.click(screen.getByRole('button', { name: 'Remove Camping Tent' }))
    await user.click(screen.getByRole('button', { name: 'Remove Old Shoes' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Go to checkout' })).toBeEnabled(),
    )
    expect(storedCart().map((line) => [line.sku, line.quantity])).toEqual([
      ['RS-001', 1],
      ['YM-015', 3],
    ])
  })

  it('says when the cart is empty', async () => {
    fakeOrders([SHOES])
    renderApp('/cart')

    expect(await screen.findByText('Your cart is empty.')).toBeVisible()
    expect(screen.getByRole('link', { name: 'Continue shopping' })).toHaveAttribute('href', '/')
    expect(screen.queryByRole('button', { name: 'Go to checkout' })).toBeNull()
  })
})

describe('paying', () => {
  it('pays with 4242, shows the confirmation and empties the cart', async () => {
    const fake = fakeOrders([SHOES])
    seedCart(cartLine(SHOES, 2))
    const { router } = renderApp('/cart')

    await user.click(await screen.findByRole('button', { name: 'Go to checkout' }))
    await fillCustomer()
    await fillCard()
    await user.click(await screen.findByRole('button', { name: 'Pay $179.98' }))

    expect(await screen.findByRole('heading', { name: 'Thank you, Ana Souza' })).toBeVisible()
    const order = [...fake.orders.values()][0]
    expect(router.state.location.pathname).toBe(`/orders/${order.id}`)
    expect(screen.getByText('Your order is paid.')).toBeVisible()
    expect(screen.getByText('Paid with the card ending in 4242.')).toBeVisible()
    expect(screen.getByText('Total: $179.98')).toBeVisible()
    expect(screen.getByText(order.id)).toBeVisible()
    expect(fake.placed[0].body).toEqual({
      customer: { name: 'Ana Souza', email: 'ana@example.com' },
      lines: [{ sku: 'RS-001', quantity: 2 }],
      payment: {
        card_number: '4242 4242 4242 4242',
        expiry_month: 12,
        expiry_year: 2030,
        cvc: '123',
      },
    })
    expect(fake.placed[0].key).toMatch(/^[0-9a-f-]{36}$/)
    expect(storedCart()).toEqual([])
    expect(screen.getByRole('link', { name: 'Cart: 0 items' })).toBeVisible()
  })

  it('creates one order when Pay is double-clicked', async () => {
    const fake = fakeOrders([SHOES])
    seedCart(cartLine(SHOES, 1))
    renderApp('/checkout')
    await fillCustomer()
    await fillCard()

    await user.dblClick(await screen.findByRole('button', { name: 'Pay $89.99' }))

    expect(await screen.findByRole('heading', { name: 'Thank you, Ana Souza' })).toBeVisible()
    expect(fake.orders.size).toBe(1)
    expect(new Set(fake.placed.map((attempt) => attempt.key)).size).toBe(1)
    expect(fake.shop.get('RS-001')?.stock).toBe(9)
  })

  it('explains a declined card and lets the shopper pay with another one', async () => {
    const fake = fakeOrders([SHOES])
    seedCart(cartLine(SHOES, 1))
    renderApp('/checkout')
    await fillCustomer()
    await fillCard('4000 0000 0000 0002')

    await user.click(await screen.findByRole('button', { name: 'Pay $89.99' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Your card was declined.')
    expect(alert).toHaveTextContent(
      'Nothing was charged and nothing was taken from stock. Try another card.',
    )
    expect(screen.getByLabelText('Card number')).toHaveValue('')
    expect(screen.getByLabelText('Name')).toHaveValue('Ana Souza')
    expect(storedCart()).toHaveLength(1)
    await fillCard()
    await user.click(payButton())

    expect(await screen.findByRole('heading', { name: 'Thank you, Ana Souza' })).toBeVisible()
    expect(fake.placed).toHaveLength(2)
    expect(fake.placed[0].key).not.toBe(fake.placed[1].key)
    expect(fake.shop.get('RS-001')?.stock).toBe(9)
  })

  it('shows which items ran short and fixes the cart in one click', async () => {
    const fake = fakeOrders([SHOES, MAT])
    seedCart(cartLine(SHOES, 2), cartLine(MAT, 1))
    const { router } = renderApp('/checkout')
    await fillCustomer()
    await fillCard()
    await screen.findByRole('button', { name: 'Pay $204.98' })
    fake.setStock('RS-001', 1)

    await user.click(payButton())

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Some items are no longer available in that quantity.')
    expect(alert).toHaveTextContent('Running Shoes: you asked for 2, 1 available.')
    await user.click(within(alert).getByRole('button', { name: 'Fix my cart' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/cart'))
    expect(await screen.findByLabelText('Quantity of Running Shoes')).toHaveValue(1)
    expect(await screen.findByText('Subtotal: $114.99')).toBeVisible()
    expect(fake.orders.size).toBe(0)
  })

  it('removes products that can no longer be sold when the cart is fixed', async () => {
    const fake = fakeOrders([SHOES, MAT])
    seedCart(cartLine(SHOES, 1), cartLine(MAT, 1))
    renderApp('/checkout')
    await fillCustomer()
    await fillCard()
    await screen.findByRole('button', { name: 'Pay $114.99' })
    fake.setStock('YM-015', 0)

    await user.click(payButton())

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Yoga Mat is out of stock.')
    await user.click(within(alert).getByRole('button', { name: 'Fix my cart' }))

    await screen.findByRole('heading', { name: 'Your cart' })
    expect(storedCart().map((line) => line.sku)).toEqual(['RS-001'])
  })

  it('pays for free gifts without asking for a card', async () => {
    const fake = fakeOrders([GIFT])
    seedCart(cartLine(GIFT, 2))
    renderApp('/checkout')
    await fillCustomer()

    expect(await screen.findByText('This order is free. No card is needed.')).toBeVisible()
    expect(screen.queryByLabelText('Card number')).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Place free order' }))

    expect(await screen.findByRole('heading', { name: 'Thank you, Ana Souza' })).toBeVisible()
    expect(screen.getByText('No card was needed: this order was free.')).toBeVisible()
    expect(fake.placed[0].body.payment).toBeUndefined()
  })

  it('keeps the same key when retrying after a lost connection', async () => {
    const fake = fakeOrders([SHOES])
    seedCart(cartLine(SHOES, 1))
    renderApp('/checkout')
    await fillCustomer()
    await fillCard()
    await screen.findByRole('button', { name: 'Pay $89.99' })
    fake.failNext(HttpResponse.error())

    await user.click(payButton())

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "The shop could not be reached. Press Pay again: you won't be charged twice.",
    )
    await user.click(payButton())
    expect(await screen.findByRole('heading', { name: 'Thank you, Ana Souza' })).toBeVisible()
    expect(fake.placed.map((attempt) => attempt.key)).toEqual([
      fake.placed[0].key,
      fake.placed[0].key,
    ])
    expect(fake.orders.size).toBe(1)
  })

  it('keeps the same key when the shop is busy', async () => {
    const fake = fakeOrders([SHOES])
    seedCart(cartLine(SHOES, 1))
    renderApp('/checkout')
    await fillCustomer()
    await fillCard()
    await screen.findByRole('button', { name: 'Pay $89.99' })
    fake.failNext(
      problem({ status: 503, slug: 'service-unavailable', title: 'The service is busy.' }),
    )

    await user.click(payButton())
    await screen.findByRole('alert')
    await user.click(payButton())

    expect(await screen.findByRole('heading', { name: 'Thank you, Ana Souza' })).toBeVisible()
    expect(new Set(fake.placed.map((attempt) => attempt.key)).size).toBe(1)
  })

  it('uses a new key once the form changes', async () => {
    const fake = fakeOrders([SHOES])
    seedCart(cartLine(SHOES, 1))
    renderApp('/checkout')
    await fillCustomer()
    await fillCard()
    await screen.findByRole('button', { name: 'Pay $89.99' })
    fake.failNext(HttpResponse.error())
    await user.click(payButton())
    await screen.findByRole('alert')

    await user.type(screen.getByLabelText('Name'), ' Lima')
    await user.click(payButton())

    expect(await screen.findByRole('heading', { name: 'Thank you, Ana Souza Lima' })).toBeVisible()
    expect(fake.placed[0].key).not.toBe(fake.placed[1].key)
  })

  it('puts the server field errors under the matching fields', async () => {
    const fake = fakeOrders([SHOES])
    seedCart(cartLine(SHOES, 1))
    renderApp('/checkout')
    await fillCustomer()
    await fillCard()
    await screen.findByRole('button', { name: 'Pay $89.99' })
    fake.failNext(
      validationProblem([
        { field: 'customer.email', code: 'invalid_email', message: 'Use a real address.' },
        { field: 'payment.expiry', code: 'card_expired', message: 'This card has expired.' },
      ]),
    )

    await user.click(payButton())

    expect(await screen.findByText('Use a real address.')).toBeVisible()
    expect(screen.getByText('This card has expired.')).toBeVisible()
    expect(screen.getByLabelText('Email')).toHaveAttribute('aria-invalid', 'true')
  })

  it('checks the form in the browser before sending anything', async () => {
    const fake = fakeOrders([SHOES])
    seedCart(cartLine(SHOES, 1))
    renderApp('/checkout')
    await screen.findByRole('button', { name: 'Pay $89.99' })
    await user.type(screen.getByLabelText('Email'), 'nope')
    await fillCard('4242 4242 4242 4241', '13/30', '12')

    await user.click(payButton())

    expect(await screen.findByText('Enter your name.')).toBeVisible()
    expect(screen.getByText('Enter an email address like name@example.com.')).toBeVisible()
    expect(screen.getByText('This card number is not valid.')).toBeVisible()
    expect(screen.getByText('Use the format MM/YY.')).toBeVisible()
    expect(screen.getByText('The security code is the 3 or 4 digits on the card.')).toBeVisible()
    expect(fake.placed).toEqual([])
  })

  it('refuses an expired card in the browser', async () => {
    const fake = fakeOrders([SHOES])
    seedCart(cartLine(SHOES, 1))
    renderApp('/checkout')
    await fillCustomer()
    await fillCard('4242 4242 4242 4242', '01/20')

    await user.click(await screen.findByRole('button', { name: 'Pay $89.99' }))

    expect(await screen.findByText('This card has expired.')).toBeVisible()
    expect(fake.placed).toEqual([])
  })

  it('sends a shopper with problems in the cart back to the cart', async () => {
    fakeOrders([SHOES, TENT])
    seedCart(cartLine(SHOES, 1), cartLine(TENT, 1))
    renderApp('/checkout')

    expect(await screen.findByText('Some items in your cart need attention.')).toBeVisible()
    expect(screen.getByRole('link', { name: 'Back to the cart' })).toHaveAttribute('href', '/cart')
    expect(screen.queryByRole('button', { name: /^Pay / })).toBeNull()
  })

  it('has nothing to pay for with an empty cart', async () => {
    fakeOrders([SHOES])
    renderApp('/checkout')

    expect(await screen.findByText('Your cart is empty.')).toBeVisible()
    expect(screen.queryByRole('button', { name: /^Pay / })).toBeNull()
  })
})

describe('the confirmation page', () => {
  it('says when an order does not exist', async () => {
    fakeOrders([SHOES])
    renderApp('/orders/00000000-0000-4000-9000-000000000999')

    expect(await screen.findByText('This order was not found.')).toBeVisible()
  })
})

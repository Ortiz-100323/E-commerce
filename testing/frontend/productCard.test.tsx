import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent, { type UserEvent } from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import { categoryLook, LOW_STOCK } from '../../frontend/src/features/storefront/categoryLook'
import { fakeCatalog } from './support/fakeCatalog'
import { renderApp } from './support/renderApp'

const PHOTO = 'https://images.example.com/speaker.jpg'

const CATALOG = [
  {
    sku: 'BS-021',
    name: 'Bluetooth Speaker',
    category: 'Electronics',
    price: '59.99',
    stock: 110,
    image_url: PHOTO,
  },
  { sku: 'BS-099', name: 'Bluetooth Speaker', category: 'Electronics', price: '24.99', stock: 3 },
  { sku: 'TS-002', name: 'Trail Shoes', category: 'Sports', price: '120.00', stock: 0 },
  { sku: 'GC-001', name: 'Gift Card', category: 'Gifts', price: '0.00', gift: true, stock: 1 },
  { sku: 'YM-015', name: 'Yoga Mat', category: 'Sports', price: '25.00', stock: LOW_STOCK + 1 },
]

let user: UserEvent

beforeEach(() => {
  user = userEvent.setup()
})

async function card(name: string | RegExp) {
  return within(await screen.findByRole('listitem', { name }))
}

function cartCount() {
  return screen.getByRole('link', { name: /^Cart: / }).textContent
}

describe('the product card', () => {
  it('tells two products with the same name apart by their SKU', async () => {
    fakeCatalog(CATALOG)
    renderApp('/')

    const cheap = await card(/^Bluetooth Speaker SKU BS-099$/)
    const dear = await card(/^Bluetooth Speaker SKU BS-021$/)

    expect(cheap.getByText('SKU BS-099')).toBeVisible()
    expect(cheap.getByText('$24.99')).toBeVisible()
    expect(dear.getByText('SKU BS-021')).toBeVisible()
    expect(dear.getByText('$59.99')).toBeVisible()
  })

  it('shows no SKU on a card whose name is unique on the page', async () => {
    fakeCatalog(CATALOG)
    renderApp('/')

    const shoes = await card('Trail Shoes')
    const gift = await card('Gift Card')

    expect(shoes.queryByText(/^SKU /)).toBeNull()
    expect(gift.queryByText(/^SKU /)).toBeNull()
  })

  it('keeps the button compact and the price on the same row', async () => {
    fakeCatalog([CATALOG[4]])
    renderApp('/')
    const mat = await card('Yoga Mat')

    const button = mat.getByRole('button', { name: 'Add to cart' })
    expect(button.parentElement).toContainElement(mat.getByText('$25.00'))
  })

  it('shows the photo when there is one, and the category placeholder otherwise', async () => {
    fakeCatalog(CATALOG)
    const { container } = renderApp('/')

    const withPhoto = await screen.findByRole('listitem', { name: /SKU BS-021$/ })
    const withoutPhoto = screen.getByRole('listitem', { name: /SKU BS-099$/ })

    expect(withPhoto.querySelector('img')).toHaveAttribute('src', PHOTO)
    expect(withPhoto.querySelector('img')).toHaveAttribute('loading', 'lazy')
    expect(withoutPhoto.querySelector('img')).toBeNull()
    const placeholder = withoutPhoto.querySelector('[data-placeholder]')
    expect(placeholder).toHaveAttribute('data-placeholder', 'Electronics')
    expect(placeholder).toHaveAttribute('aria-hidden', 'true')
    expect(container.querySelectorAll('[data-placeholder] svg').length).toBeGreaterThan(0)
  })

  it('falls back to the placeholder when the photo fails to load', async () => {
    fakeCatalog(CATALOG)
    renderApp('/')
    const withPhoto = await screen.findByRole('listitem', { name: /SKU BS-021$/ })

    fireEvent.error(withPhoto.querySelector('img') as HTMLImageElement)

    await waitFor(() => expect(withPhoto.querySelector('img')).toBeNull())
    expect(withPhoto.querySelector('[data-placeholder]')).toHaveAttribute(
      'data-placeholder',
      'Electronics',
    )
  })

  it('shows the name, a softer category and the price, with Free for gifts', async () => {
    fakeCatalog(CATALOG)
    renderApp('/')

    const gift = await card('Gift Card')

    expect(gift.getByRole('link', { name: 'Gift Card' })).toBeVisible()
    expect(gift.getByText('Gifts')).toBeVisible()
    expect(gift.getByText('Free')).toBeVisible()
  })

  it('warns when few are left and disables buying when none are', async () => {
    fakeCatalog(CATALOG)
    renderApp('/')

    const low = await card(/SKU BS-099$/)
    const plenty = await card('Yoga Mat')
    const soldOut = await card('Trail Shoes')

    expect(low.getByText('Only 3 left')).toBeVisible()
    expect(plenty.queryByText(/^Only/)).toBeNull()
    expect(plenty.getByText('In stock')).toBeVisible()
    expect(soldOut.getByText('Out of stock')).toBeVisible()
    expect(soldOut.getByRole('button', { name: 'Add to cart' })).toBeDisabled()
  })

  it('adds to the cart from the card and stops at the stock', async () => {
    fakeCatalog(CATALOG)
    renderApp('/')
    const gift = await card('Gift Card')

    await user.click(gift.getByRole('button', { name: 'Add to cart' }))

    expect(cartCount()).toBe('Cart: 1 item')
    expect(gift.getByRole('status')).toHaveTextContent('Gift Card added to cart (1 in your cart).')
    const button = gift.getByRole('button', { name: 'All 1 in your cart' })
    expect(button).toBeDisabled()
    await user.click(button)
    expect(cartCount()).toBe('Cart: 1 item')
  })

  it('opens the product page from the card', async () => {
    fakeCatalog(CATALOG)
    const { router } = renderApp('/')
    const shoes = await card('Trail Shoes')

    await user.click(shoes.getByRole('link', { name: 'Trail Shoes' }))

    await waitFor(() => expect(router.state.location.pathname.startsWith('/products/')).toBe(true))
  })

  it('works with the keyboard: Tab reaches the link, then the button', async () => {
    fakeCatalog([CATALOG[1]])
    renderApp('/')
    const speaker = await card('Bluetooth Speaker')
    const link = speaker.getByRole('link', { name: 'Bluetooth Speaker' })
    const button = speaker.getByRole('button', { name: 'Add to cart' })

    link.focus()
    await user.tab()
    expect(button).toHaveFocus()
    await user.keyboard('{Enter}')
    await user.keyboard(' ')

    expect(cartCount()).toBe('Cart: 2 items')
  })
})

describe('the category look', () => {
  it('gives every category the same colour and icon every time', () => {
    expect(categoryLook('Electronics')).toEqual(categoryLook(' electronics '))
    expect(categoryLook('Sports').icon).toBe('sports')
    expect(categoryLook('Home & Office').icon).toBe('home')
    expect(categoryLook('Something new').icon).toBe('box')
  })

  it('spreads categories over different colours', () => {
    const colours = new Set(
      ['Electronics', 'Sports', 'Home & Office', 'Kitchen', 'Gifts', 'Books'].map(
        (category) => categoryLook(category).tint,
      ),
    )

    expect(colours.size).toBeGreaterThan(3)
  })
})

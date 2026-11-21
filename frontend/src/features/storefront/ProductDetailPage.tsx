import { useState } from 'react'
import { Link, useParams } from 'react-router'

import { ApiError } from '../../api/apiError'
import { useProduct } from '../../api/productQueries'
import type { Product } from '../../api/products'
import { canAdd } from '../../cart/cart'
import { useCart } from '../../cart/CartContext'
import { displayPrice } from './ProductCard'
import styles from './Storefront.module.css'

function AddToCart({ product }: { product: Product }) {
  const cart = useCart()
  const [message, setMessage] = useState('')
  const inCart = cart.quantityOf(product.id)
  const state = canAdd(cart.lines, product)

  const add = () => {
    const result = cart.add(product)
    if (result === 'added') {
      setMessage(`Added to cart (${inCart + 1} in your cart).`)
    }
  }

  let label = 'Add to cart'
  if (product.status === 'ARCHIVED') {
    label = 'No longer available'
  } else if (state === 'out_of_stock') {
    label = 'Out of stock'
  } else if (state === 'at_stock_limit') {
    label = `Only ${product.stock} in stock`
  }

  return (
    <div className={styles.buy}>
      <button type="button" className={styles.primary} disabled={state !== 'added'} onClick={add}>
        {label}
      </button>
      <p role="status" className={styles.added}>
        {message}
      </p>
    </div>
  )
}

export function ProductDetailPage() {
  const { productId = '' } = useParams()
  const product = useProduct(productId)

  if (product.isPending) {
    return <p>Loading…</p>
  }
  if (product.isError) {
    const missing = product.error instanceof ApiError && product.error.status === 404
    return (
      <section aria-labelledby="detail-title">
        <h1 id="detail-title">
          {missing ? 'Product not found' : "We couldn't load this product."}
        </h1>
        <p>
          {missing ? null : (
            <>
              <button type="button" onClick={() => void product.refetch()}>
                Try again
              </button>{' '}
            </>
          )}
          <Link to="/">Back to the shop</Link>
        </p>
      </section>
    )
  }

  const item = product.data
  return (
    <article aria-labelledby="detail-title" className={styles.detail}>
      <p>
        <Link to="/">Back to the shop</Link>
      </p>
      <h1 id="detail-title">{item.name}</h1>
      {item.status === 'ARCHIVED' ? (
        <p role="note" className={styles.notice}>
          This product is no longer available.
        </p>
      ) : null}
      <p className={styles.detailPrice}>
        {displayPrice(item)}
        {item.gift ? <span className={styles.gift}>Gift</span> : null}
      </p>
      {item.description ? <p>{item.description}</p> : null}
      <dl className={styles.facts}>
        <dt>Category</dt>
        <dd>{item.category}</dd>
        <dt>Weight</dt>
        <dd>{item.weight_kg} kg</dd>
        <dt>Availability</dt>
        <dd>{item.stock === 0 ? 'Out of stock' : `${item.stock} in stock`}</dd>
      </dl>
      <AddToCart product={item} />
    </article>
  )
}

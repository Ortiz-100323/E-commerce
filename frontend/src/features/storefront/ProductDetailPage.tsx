import { useState } from 'react'
import { Link, useParams } from 'react-router'

import { ApiError } from '../../api/apiError'
import { useProduct } from '../../api/productQueries'
import type { Product } from '../../api/products'
import { canAdd } from '../../cart/cart'
import { useCart } from '../../cart/CartContext'
import { useIsAdmin } from '../../session/session'
import controls from '../../styles/controls.module.css'
import { displayPrice, StockLabel } from './ProductCard'
import { ProductImage } from './ProductImage'
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
      <button
        type="button"
        className={`${controls.primary} ${styles.buyButton}`}
        disabled={state !== 'added'}
        onClick={add}
      >
        {label}
      </button>
      <p role="status" className={styles.added}>
        {message}
      </p>
      {inCart > 0 ? (
        <Link to="/cart" className={styles.toCart}>
          Go to your cart
        </Link>
      ) : null}
    </div>
  )
}

function BackLink() {
  return (
    <Link to="/" className={styles.back}>
      <span aria-hidden="true">‹ </span>Back to the shop
    </Link>
  )
}

export function ProductDetailPage() {
  const admin = useIsAdmin()
  const { productId = '' } = useParams()
  const product = useProduct(productId)

  if (product.isPending) {
    return <p className={styles.loading}>Loading…</p>
  }
  if (product.isError) {
    const missing = product.error instanceof ApiError && product.error.status === 404
    return (
      <section aria-labelledby="detail-title" className={styles.empty}>
        <h1 id="detail-title" className={styles.emptyTitle}>
          {missing ? 'Product not found' : "We couldn't load this product."}
        </h1>
        <p className={styles.emptyText}>
          {missing
            ? 'It may have been removed, or the link is incomplete.'
            : 'Check your connection and try again.'}
        </p>
        <p className={styles.emptyActions}>
          {missing ? null : (
            <button
              type="button"
              className={controls.secondary}
              onClick={() => void product.refetch()}
            >
              Try again
            </button>
          )}
          <Link to="/" className={controls.primary}>
            Back to the shop
          </Link>
        </p>
      </section>
    )
  }

  const item = product.data
  return (
    <article aria-labelledby="detail-title" className={styles.detail}>
      <p className={styles.crumbs}>
        <BackLink />
      </p>
      <div className={styles.detailGrid}>
        <div className={styles.gallery}>
          <ProductImage imageUrl={item.image_url} category={item.category} />
        </div>
        <div className={styles.info}>
          <h1 id="detail-title" className={styles.detailName}>
            {item.name}
          </h1>
          {item.status === 'ARCHIVED' ? (
            <p role="note" className={controls.notice}>
              This product is no longer available.
            </p>
          ) : null}
          <p className={styles.detailPrice}>
            <span>{displayPrice(item)}</span>
            {item.gift ? <span className={styles.gift}>Gift</span> : null}
          </p>
          <StockLabel product={item} />
          {admin ? (
            <p role="note" className={controls.info}>
              You're logged in as an administrator, so you can't buy here.
            </p>
          ) : (
            <AddToCart product={item} />
          )}
          {item.description ? <p className={styles.description}>{item.description}</p> : null}
          <dl className={styles.facts}>
            <dt>Category</dt>
            <dd>{item.category}</dd>
            <dt>SKU</dt>
            <dd>{item.sku}</dd>
            <dt>Weight</dt>
            <dd>{item.weight_kg} kg</dd>
            <dt>Availability</dt>
            <dd>{item.stock === 0 ? 'Out of stock' : `${item.stock} in stock`}</dd>
          </dl>
        </div>
      </div>
    </article>
  )
}

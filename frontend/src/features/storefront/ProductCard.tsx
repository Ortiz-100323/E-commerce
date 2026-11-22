import { useEffect, useId, useState } from 'react'
import { Link } from 'react-router'

import type { Product } from '../../api/products'
import { useCart } from '../../cart/CartContext'
import { canAdd } from '../../cart/cart'
import { formatPrice } from '../admin/products/format'
import { LOW_STOCK } from './categoryLook'
import styles from './ProductCard.module.css'
import { ProductImage } from './ProductImage'

const ADDED_FOR_MS = 1500

export function displayPrice(product: Product): string {
  return product.gift ? 'Free' : formatPrice(product.price, product.currency)
}

export type StockLevel = 'out' | 'low' | 'in'

export function stockLevel(product: Product): StockLevel {
  if (!product.is_sellable || product.stock <= 0) {
    return 'out'
  }
  return product.stock <= LOW_STOCK ? 'low' : 'in'
}

export function StockLabel({ product, className }: { product: Product; className?: string }) {
  const level = stockLevel(product)
  const text = { out: 'Out of stock', low: `Only ${product.stock} left`, in: 'In stock' }[level]
  return (
    <p className={`${styles.stock} ${styles[level]} ${className ?? ''}`.trim()}>
      <span className={styles.dot} aria-hidden="true" />
      {text}
    </p>
  )
}

function AddToCart({ product }: { product: Product }) {
  const cart = useCart()
  const [message, setMessage] = useState('')
  const [justAdded, setJustAdded] = useState(false)
  const inCart = cart.quantityOf(product.id)
  const state = canAdd(cart.lines, product)

  useEffect(() => {
    if (!justAdded) {
      return undefined
    }
    const timer = window.setTimeout(() => setJustAdded(false), ADDED_FOR_MS)
    return () => window.clearTimeout(timer)
  }, [justAdded])

  const add = () => {
    if (cart.add(product) === 'added') {
      setMessage(`${product.name} added to cart (${inCart + 1} in your cart).`)
      setJustAdded(true)
    }
  }

  let label = 'Add to cart'
  if (state === 'at_stock_limit') {
    label = `All ${inCart} in your cart`
  } else if (justAdded) {
    label = 'Added'
  }

  return (
    <>
      <button
        type="button"
        className={styles.add}
        disabled={state !== 'added'}
        data-added={justAdded || undefined}
        onClick={add}
      >
        {label}
      </button>
      <p role="status" className={styles.announcement}>
        {message}
      </p>
    </>
  )
}

export function ProductCard({ product, showSku = false }: { product: Product; showSku?: boolean }) {
  const id = useId()
  const nameId = `${id}-name`
  const skuId = `${id}-sku`
  return (
    <li className={styles.card} aria-labelledby={showSku ? `${nameId} ${skuId}` : nameId}>
      <div className={styles.media}>
        <ProductImage imageUrl={product.image_url} category={product.category} />
        {product.gift ? <span className={styles.gift}>Gift</span> : null}
      </div>
      <div className={styles.body}>
        <h2 className={styles.name} title={product.name}>
          <Link id={nameId} to={`/products/${product.id}`} className={styles.link}>
            {product.name}
          </Link>
        </h2>
        <p className={styles.category}>{product.category}</p>
        {showSku ? (
          <p id={skuId} className={styles.sku}>
            SKU {product.sku}
          </p>
        ) : null}
        <StockLabel product={product} />
        <div className={styles.footer}>
          <span className={styles.price}>{displayPrice(product)}</span>
          <AddToCart product={product} />
        </div>
      </div>
    </li>
  )
}

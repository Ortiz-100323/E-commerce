import { Link } from 'react-router'

import type { Product } from '../../api/products'
import { formatPrice } from '../admin/products/format'
import styles from './Storefront.module.css'

export function displayPrice(product: Product): string {
  return product.gift ? 'Free' : formatPrice(product.price, product.currency)
}

export function ProductCard({ product }: { product: Product }) {
  return (
    <li className={styles.card} aria-label={product.name}>
      <Link to={`/products/${product.id}`} className={styles.cardLink}>
        <span className={styles.cardName}>{product.name}</span>
      </Link>
      <span className={styles.cardCategory}>{product.category}</span>
      <span className={styles.cardPrice}>{displayPrice(product)}</span>
      <span className={styles.badges}>
        {product.gift ? <span className={styles.gift}>Gift</span> : null}
        {product.stock === 0 ? <span className={styles.out}>Out of stock</span> : null}
      </span>
    </li>
  )
}

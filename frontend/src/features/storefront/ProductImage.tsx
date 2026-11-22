import { useState } from 'react'

import { CategoryIcon } from './CategoryIcon'
import { categoryLook } from './categoryLook'
import styles from './ProductCard.module.css'

type ProductImageProps = { imageUrl: string | null; category: string }

export function ProductImage({ imageUrl, category }: ProductImageProps) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null)
  if (imageUrl !== null && imageUrl !== failedUrl) {
    return (
      <img
        className={styles.photo}
        src={imageUrl}
        alt=""
        loading="lazy"
        decoding="async"
        onError={() => setFailedUrl(imageUrl)}
      />
    )
  }
  const look = categoryLook(category)
  return (
    <div
      className={`${styles.placeholder} ${styles[`tone${look.tone}`]}`}
      data-placeholder={category}
      aria-hidden="true"
    >
      <CategoryIcon name={look.icon} className={styles.placeholderIcon} />
    </div>
  )
}

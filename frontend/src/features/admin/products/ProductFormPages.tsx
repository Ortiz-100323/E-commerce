import { useState } from 'react'
import { useNavigate, useParams } from 'react-router'

import type { Product } from '../../../api/products'
import { useNotify } from '../../../notifications/NotificationContext'
import { ProductForm } from './ProductForm'
import { ProductMissing } from './ProductMissing'
import { useProduct } from './queries'

function useBackToTable(title: string) {
  const navigate = useNavigate()
  const notify = useNotify()
  return (product: Product) => {
    notify({ title, detail: `${product.sku} · ${product.name}`, tone: 'success' })
    void navigate('/admin/products')
  }
}

export function NewProductPage() {
  const onSaved = useBackToTable('Product created')
  return (
    <section aria-labelledby="new-product-title">
      <h2 id="new-product-title">New product</h2>
      <ProductForm onSaved={onSaved} />
    </section>
  )
}

export function EditProductPage() {
  const { productId = '' } = useParams()
  const product = useProduct(productId)
  const onSaved = useBackToTable('Changes saved')
  const [generation, setGeneration] = useState(0)

  const reload = async () => {
    await product.refetch()
    setGeneration((value) => value + 1)
  }

  if (product.isPending) {
    return <p>Loading…</p>
  }
  if (product.isError) {
    return <ProductMissing error={product.error} onRetry={() => void product.refetch()} />
  }
  return (
    <section aria-labelledby="edit-product-title">
      <h2 id="edit-product-title">Edit {product.data.name}</h2>
      <ProductForm
        key={generation}
        product={product.data}
        onSaved={onSaved}
        onReload={() => void reload()}
      />
    </section>
  )
}

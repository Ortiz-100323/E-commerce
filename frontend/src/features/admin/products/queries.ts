import { useMutation, useQueryClient } from '@tanstack/react-query'

import {
  productsApi,
  type NewProduct,
  type Product,
  type ProductUpdate,
} from '../../../api/products'
import { productKeys } from '../../../api/productQueries'
import type { MutationMeta } from '../../../app/queryClient'

export {
  productKeys,
  useCategories,
  useProduct,
  useProductHistory,
  useProductList,
} from '../../../api/productQueries'

function useRefreshAfterChange() {
  const client = useQueryClient()
  return async (product: Product) => {
    client.setQueryData(productKeys.detail(product.id), product)
    await Promise.all([
      client.invalidateQueries({ queryKey: productKeys.lists, refetchType: 'all' }),
      client.invalidateQueries({ queryKey: productKeys.history(product.id) }),
      client.invalidateQueries({ queryKey: productKeys.categories }),
    ])
  }
}

const formMeta: MutationMeta = { handledProblems: ['duplicate-sku', 'version-conflict'] }

export function useCreateProduct() {
  const refresh = useRefreshAfterChange()
  return useMutation({
    mutationFn: (product: NewProduct) => productsApi.create(product),
    onSuccess: refresh,
    meta: formMeta,
  })
}

export function useUpdateProduct(id: string) {
  const refresh = useRefreshAfterChange()
  return useMutation({
    mutationFn: (update: ProductUpdate) => productsApi.update(id, update),
    onSuccess: refresh,
    meta: formMeta,
  })
}

export function useArchiveProduct() {
  const refresh = useRefreshAfterChange()
  return useMutation({
    mutationFn: (id: string) => productsApi.archive(id),
    onSuccess: refresh,
  })
}

export function useRestoreProduct() {
  const refresh = useRefreshAfterChange()
  return useMutation({
    mutationFn: (id: string) => productsApi.restore(id),
    onSuccess: refresh,
  })
}

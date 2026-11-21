import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useRequiredActor } from '../../../actor/ActorContext'
import {
  productsApi,
  type NewProduct,
  type Product,
  type ProductQuery,
  type ProductUpdate,
} from '../../../api/products'
import type { MutationMeta } from '../../../app/queryClient'

export const productKeys = {
  all: ['products'] as const,
  lists: ['products', 'list'] as const,
  list: (query: ProductQuery) => ['products', 'list', query] as const,
  detail: (id: string) => ['products', 'detail', id] as const,
  history: (id: string) => ['products', 'history', id] as const,
  categories: ['categories'] as const,
}

export function useProductList(query: ProductQuery) {
  return useQuery({
    queryKey: productKeys.list(query),
    queryFn: () => productsApi.search(query),
    placeholderData: (previous) => previous,
  })
}

export function useProduct(id: string) {
  return useQuery({
    queryKey: productKeys.detail(id),
    queryFn: () => productsApi.get(id),
    meta: pageMeta,
  })
}

export function useProductHistory(id: string) {
  return useQuery({
    queryKey: productKeys.history(id),
    queryFn: () => productsApi.history(id),
    meta: pageMeta,
  })
}

export function useCategories() {
  return useQuery({ queryKey: productKeys.categories, queryFn: () => productsApi.categories() })
}

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
const pageMeta: MutationMeta = { handledProblems: ['not-found'] }

export function useCreateProduct() {
  const actor = useRequiredActor()
  const refresh = useRefreshAfterChange()
  return useMutation({
    mutationFn: (product: NewProduct) => productsApi.create(product, actor),
    onSuccess: refresh,
    meta: formMeta,
  })
}

export function useUpdateProduct(id: string) {
  const actor = useRequiredActor()
  const refresh = useRefreshAfterChange()
  return useMutation({
    mutationFn: (update: ProductUpdate) => productsApi.update(id, update, actor),
    onSuccess: refresh,
    meta: formMeta,
  })
}

export function useArchiveProduct() {
  const actor = useRequiredActor()
  const refresh = useRefreshAfterChange()
  return useMutation({
    mutationFn: (id: string) => productsApi.archive(id, actor),
    onSuccess: refresh,
  })
}

export function useRestoreProduct() {
  const actor = useRequiredActor()
  const refresh = useRefreshAfterChange()
  return useMutation({
    mutationFn: (id: string) => productsApi.restore(id, actor),
    onSuccess: refresh,
  })
}

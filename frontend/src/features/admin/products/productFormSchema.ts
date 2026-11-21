import { z } from 'zod'

import type { Product, ProductFields } from '../../../api/products'

const required = (label: string) =>
  z
    .string()
    .trim()
    .min(1, { message: `${label} is required.` })

const productFormFields = z.object({
  sku: z.string(),
  name: required('Name'),
  description: z.string(),
  category: required('Category'),
  price: z
    .string()
    .trim()
    .regex(/^\d+(\.\d{1,2})?$/, { message: 'Use a number with at most 2 decimals, like 19.99.' }),
  stock: z.string().trim().regex(/^\d+$/, { message: 'Use a whole number of 0 or more.' }),
  weight_kg: z
    .string()
    .trim()
    .regex(/^\d+(\.\d{1,3})?$/, { message: 'Use a number with at most 3 decimals, like 0.250.' }),
  gift: z.boolean(),
})

export const GIFT_MUST_BE_FREE = 'A gift must be free. Set the price to 0, or untick the gift.'

function giftRule(values: { gift: boolean; price: string }, context: z.RefinementCtx): void {
  if (values.gift && !isZeroPrice(values.price)) {
    context.addIssue({ code: 'custom', path: ['price'], message: GIFT_MUST_BE_FREE })
  }
}

export const productFormSchema = productFormFields.superRefine(giftRule)

export const createProductFormSchema = productFormFields
  .extend({ sku: z.string().trim().min(1, { message: 'SKU is required.' }) })
  .superRefine(giftRule)

export type ProductFormValues = z.input<typeof productFormFields>

export const PRODUCT_FORM_FIELDS = [
  'sku',
  'name',
  'description',
  'category',
  'price',
  'stock',
  'weight_kg',
  'gift',
] as const

export const emptyProductForm: ProductFormValues = {
  sku: '',
  name: '',
  description: '',
  category: '',
  price: '',
  stock: '0',
  weight_kg: '',
  gift: false,
}

export function formValuesOf(product: Product): ProductFormValues {
  return {
    sku: product.sku,
    name: product.name,
    description: product.description,
    category: product.category,
    price: product.price,
    stock: String(product.stock),
    weight_kg: product.weight_kg,
    gift: product.gift,
  }
}

export function fieldsOf(values: ProductFormValues): ProductFields {
  return {
    name: values.name.trim(),
    description: values.description,
    category: values.category.trim(),
    price: values.price.trim(),
    stock: Number(values.stock.trim()),
    weight_kg: values.weight_kg.trim(),
    gift: values.gift,
  }
}

export function isZeroPrice(price: string): boolean {
  return /^\d+(\.\d+)?$/.test(price.trim()) && Number(price) === 0
}

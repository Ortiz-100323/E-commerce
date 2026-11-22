import { zodResolver } from '@hookform/resolvers/zod'
import { useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router'

import { ApiError, type FieldProblem } from '../../../api/apiError'
import type { Product } from '../../../api/products'
import { ConfirmDialog } from '../../../components/ConfirmDialog'
import { applyProblemToForm } from '../../../forms/applyProblemToForm'
import { FormProblems } from '../../../forms/FormProblems'
import formStyles from '../../../forms/Forms.module.css'
import { TextAreaField } from '../../../forms/TextAreaField'
import { TextField } from '../../../forms/TextField'
import {
  emptyProductForm,
  fieldsOf,
  imageUrlProblem,
  formValuesOf,
  isZeroPrice,
  PRODUCT_FORM_FIELDS,
  createProductFormSchema,
  productFormSchema,
  type ProductFormValues,
} from './productFormSchema'
import styles from './Products.module.css'
import { useCategories, useCreateProduct, useUpdateProduct } from './queries'

type ProductFormProps = {
  product?: Product
  onSaved: (product: Product) => void
  onReload?: () => void
}

export function ProductForm({ product: current, onSaved, onReload }: ProductFormProps) {
  const [product] = useState(current)
  const editing = product !== undefined
  const create = useCreateProduct()
  const update = useUpdateProduct(product?.id ?? '')
  const categories = useCategories()
  const saving = create.isPending || update.isPending
  const [problems, setProblems] = useState<FieldProblem[]>([])
  const [conflict, setConflict] = useState(false)
  const [askingGift, setAskingGift] = useState(false)
  const waiting = useRef<ProductFormValues | null>(null)

  const {
    register,
    handleSubmit,
    setError,
    setFocus,
    setValue,
    getValues,
    watch,
    formState: { errors },
  } = useForm<ProductFormValues>({
    resolver: zodResolver(editing ? productFormSchema : createProductFormSchema),
    defaultValues: product ? formValuesOf(product) : emptyProductForm,
  })
  const gift = watch('gift')
  const imageUrl = watch('image_url')
  const priceBeforeGift = useRef('')

  const giftField = register('gift', {
    onChange: (event: { target: { checked: boolean } }) => {
      if (event.target.checked) {
        priceBeforeGift.current = getValues('price')
        setValue('price', '0', { shouldValidate: false })
      } else if (isZeroPrice(getValues('price')) && priceBeforeGift.current !== '') {
        setValue('price', priceBeforeGift.current, { shouldValidate: false })
      }
    },
  })

  const showError = (error: unknown) => {
    if (error instanceof ApiError && error.problem === 'duplicate-sku') {
      setError(
        'sku',
        { type: error.problem, message: error.detail ?? error.title },
        { shouldFocus: true },
      )
      return
    }
    if (error instanceof ApiError && error.problem === 'version-conflict') {
      setConflict(true)
      return
    }
    setProblems(applyProblemToForm(error, PRODUCT_FORM_FIELDS, setError))
  }

  const save = (values: ProductFormValues) => {
    if (saving) {
      return
    }
    setProblems([])
    setConflict(false)
    const callbacks = { onSuccess: onSaved, onError: showError }
    if (product) {
      update.mutate({ ...fieldsOf(values), version: product.version }, callbacks)
    } else {
      create.mutate({ ...fieldsOf(values), sku: values.sku.trim() }, callbacks)
    }
  }

  const submit = handleSubmit((values) => {
    if (isZeroPrice(values.price) && !values.gift) {
      waiting.current = values
      setAskingGift(true)
      return
    }
    save(values)
  })

  const confirmGift = () => {
    const values = waiting.current
    setAskingGift(false)
    setValue('gift', true)
    if (values) {
      save({ ...values, gift: true })
    }
  }

  const declineGift = () => {
    setAskingGift(false)
    waiting.current = null
    setFocus('price')
  }

  return (
    <form onSubmit={submit} noValidate className={styles.form}>
      {conflict ? (
        <div role="alert" className={formStyles.banner}>
          <p>
            This product was changed by someone else since you opened it. Reload to see the latest
            version; your unsaved changes will be lost.
          </p>
          <button type="button" onClick={onReload}>
            Reload
          </button>
        </div>
      ) : null}
      <FormProblems problems={problems} />
      <label className={formStyles.checkbox}>
        <input type="checkbox" {...giftField} />
        Free gift (gifts are always priced at 0)
      </label>
      <TextField
        label="SKU"
        readOnly={editing}
        autoComplete="off"
        error={errors.sku}
        {...register('sku')}
      />
      <TextField label="Name" error={errors.name} {...register('name')} />
      <TextAreaField label="Description" error={errors.description} {...register('description')} />
      <TextField
        label="Category"
        list="category-suggestions"
        autoComplete="off"
        error={errors.category}
        {...register('category')}
      />
      <datalist id="category-suggestions">
        {(categories.data?.items ?? []).map((name) => (
          <option key={name} value={name} />
        ))}
      </datalist>
      <div className={styles.row}>
        <TextField
          label="Price (USD)"
          inputMode="decimal"
          readOnly={gift}
          hint={gift ? 'Gifts are always free.' : undefined}
          error={errors.price}
          {...register('price')}
        />
        <TextField label="Stock" inputMode="numeric" error={errors.stock} {...register('stock')} />
        <TextField
          label="Weight (kg)"
          inputMode="decimal"
          error={errors.weight_kg}
          {...register('weight_kg')}
        />
      </div>
      <TextField
        label="Image URL (optional)"
        type="url"
        inputMode="url"
        autoComplete="off"
        placeholder="https://"
        hint="A photo address starting with https://. Without one, the shop shows the category's placeholder."
        error={errors.image_url}
        {...register('image_url')}
      />
      {imageUrl.trim() !== '' && imageUrlProblem(imageUrl) === null ? (
        <img src={imageUrl.trim()} alt="Image preview" className={styles.imagePreview} />
      ) : null}
      <div className={styles.actions}>
        <Link to="/admin/products">Cancel</Link>
        <button type="submit" disabled={saving} className={styles.primary}>
          {saving ? 'Saving…' : editing ? 'Save changes' : 'Create product'}
        </button>
      </div>
      {askingGift ? (
        <ConfirmDialog
          title="Price is 0. Mark this product as a gift?"
          message="A product can only be free if it is a gift."
          confirmLabel="Yes, mark as gift"
          cancelLabel="No, go back"
          onConfirm={confirmGift}
          onCancel={declineGift}
        />
      ) : null}
    </form>
  )
}

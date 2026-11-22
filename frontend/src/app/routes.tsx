import { Navigate, type RouteObject } from 'react-router'

import { AdminLayout } from '../features/admin/AdminLayout'
import { ImportReviewPage } from '../features/admin/imports/ImportReviewPage'
import { ImportUploadPage } from '../features/admin/imports/ImportUploadPage'
import { EditProductPage, NewProductPage } from '../features/admin/products/ProductFormPages'
import { ProductHistoryPage } from '../features/admin/products/ProductHistoryPage'
import { ProductsTablePage } from '../features/admin/products/ProductsTablePage'
import { CartPage } from '../features/storefront/checkout/CartPage'
import { CheckoutPage } from '../features/storefront/checkout/CheckoutPage'
import { OrderConfirmationPage } from '../features/storefront/checkout/OrderConfirmationPage'
import { ProductDetailPage } from '../features/storefront/ProductDetailPage'
import { StorefrontPage } from '../features/storefront/StorefrontPage'
import { AppShell } from './AppShell'
import { NotFoundPage } from './NotFoundPage'

export const routes: RouteObject[] = [
  {
    element: <AppShell />,
    children: [
      { index: true, element: <StorefrontPage /> },
      { path: 'products/:productId', element: <ProductDetailPage /> },
      { path: 'cart', element: <CartPage /> },
      { path: 'checkout', element: <CheckoutPage /> },
      { path: 'orders/:orderId', element: <OrderConfirmationPage /> },
      {
        path: 'admin',
        element: <AdminLayout />,
        children: [
          { index: true, element: <Navigate to="products" replace /> },
          { path: 'products', element: <ProductsTablePage /> },
          { path: 'products/new', element: <NewProductPage /> },
          { path: 'products/:productId/edit', element: <EditProductPage /> },
          { path: 'products/:productId/history', element: <ProductHistoryPage /> },
          { path: 'imports/new', element: <ImportUploadPage /> },
          { path: 'imports/:importId', element: <ImportReviewPage /> },
        ],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

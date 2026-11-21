import { Navigate, type RouteObject } from 'react-router'

import { AdminLayout } from '../features/admin/AdminLayout'
import { AdminProductsPage } from '../features/admin/AdminProductsPage'
import { StorefrontPage } from '../features/storefront/StorefrontPage'
import { WeatherPage } from '../features/weather/WeatherPage'
import { AppShell } from './AppShell'
import { NotFoundPage } from './NotFoundPage'

export const routes: RouteObject[] = [
  {
    element: <AppShell />,
    children: [
      { index: true, element: <StorefrontPage /> },
      {
        path: 'admin',
        element: <AdminLayout />,
        children: [
          { index: true, element: <Navigate to="products" replace /> },
          { path: 'products', element: <AdminProductsPage /> },
        ],
      },
      { path: 'weather', element: <WeatherPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

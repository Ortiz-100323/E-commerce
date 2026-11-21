import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider, type RouteObject } from 'react-router'

import { AppProviders } from '../../../frontend/src/app/AppProviders'
import { routes as appRoutes } from '../../../frontend/src/app/routes'

type Options = {
  routes?: RouteObject[]
}

export function renderApp(path: string, { routes = appRoutes }: Options = {}) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const view = render(
    <AppProviders retryDelay={() => 0}>
      <RouterProvider router={router} />
    </AppProviders>,
  )
  return { ...view, router }
}

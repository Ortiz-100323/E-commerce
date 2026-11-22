import { http, HttpResponse } from 'msw/http'
import { setupServer } from 'msw/node'

import { myOrdersHandler, sessionHandlers } from './fakeSession'

const defaults = [
  http.get('*/api/v1/products', () =>
    HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20 }),
  ),
  http.get('*/api/v1/categories', () => HttpResponse.json({ items: [] })),
]

export const server = setupServer(...defaults, ...sessionHandlers, myOrdersHandler)

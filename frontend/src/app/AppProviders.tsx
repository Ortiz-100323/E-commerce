import { QueryClientProvider } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'

import { CartProvider } from '../cart/CartContext'
import { NotificationProvider, useNotify } from '../notifications/NotificationContext'
import { createQueryClient } from './queryClient'

type Props = {
  children: ReactNode
  retryDelay?: (attempt: number) => number
}

function QueryProvider({ children, retryDelay }: Props) {
  const notify = useNotify()
  const [client] = useState(() => createQueryClient({ notify, retryDelay }))
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

export function AppProviders({ children, retryDelay }: Props) {
  return (
    <NotificationProvider>
      <CartProvider>
        <QueryProvider retryDelay={retryDelay}>{children}</QueryProvider>
      </CartProvider>
    </NotificationProvider>
  )
}

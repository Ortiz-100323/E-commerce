import type { ReactNode } from 'react'

import type { CategoryIconName } from './categoryLook'

const SHAPES: Record<CategoryIconName, ReactNode> = {
  electronics: (
    <>
      <rect x="6" y="3" width="12" height="18" rx="2" />
      <circle cx="12" cy="14" r="3.5" />
      <circle cx="12" cy="7" r="1" />
    </>
  ),
  sports: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M3.5 12h17M12 3.5c3 2.6 3 14.4 0 17M12 3.5c-3 2.6-3 14.4 0 17" />
    </>
  ),
  home: (
    <>
      <path d="M4 11.5 12 4l8 7.5" />
      <path d="M6.5 9.5V20h11V9.5M10 20v-5.5h4V20" />
    </>
  ),
  kitchen: (
    <>
      <path d="M4 10h16v3a6 6 0 0 1-6 6h-4a6 6 0 0 1-6-6z" />
      <path d="M2 10h2m16 0h2M9 4.5c0 1.5 1 1.5 1 3M13 4.5c0 1.5 1 1.5 1 3" />
    </>
  ),
  gift: (
    <>
      <rect x="4" y="9" width="16" height="11" rx="1" />
      <path d="M3 9h18M12 9v11M12 9c-1.5-4-6-4-6-1.5S9 9 12 9c3 0 6 0 6-1.5S13.5 5 12 9" />
    </>
  ),
  book: (
    <>
      <path d="M5 4.5h10.5a2.5 2.5 0 0 1 2.5 2.5v13H7.5A2.5 2.5 0 0 1 5 17.5z" />
      <path d="M5 17.5A2.5 2.5 0 0 1 7.5 15H18M9 8h5" />
    </>
  ),
  outdoors: (
    <>
      <path d="M2.5 19.5 9 8l4 7 2.5-4 6 8.5z" />
      <circle cx="17" cy="6" r="2" />
    </>
  ),
  beauty: (
    <>
      <rect x="8" y="9" width="8" height="11.5" rx="2" />
      <path d="M10 9V6.5h4V9M11 3.5h2v3h-2z" />
    </>
  ),
  games: (
    <>
      <rect x="4" y="4" width="16" height="16" rx="3" />
      <circle cx="8.5" cy="8.5" r="1" />
      <circle cx="15.5" cy="15.5" r="1" />
      <circle cx="12" cy="12" r="1" />
    </>
  ),
  food: (
    <>
      <path d="M5 8h11v6a5 5 0 0 1-5 5h-1a5 5 0 0 1-5-5z" />
      <path d="M16 10h1.5a2.5 2.5 0 0 1 0 5H16M8 3.5v2M11 3.5v2" />
    </>
  ),
  tools: (
    <path d="M14.5 4.5a4.5 4.5 0 0 0-4.3 5.8L4 16.5 7.5 20l6.2-6.2a4.5 4.5 0 0 0 5.8-4.3l-2.8 2.8-3-3z" />
  ),
  health: (
    <>
      <rect x="4" y="4" width="16" height="16" rx="4" />
      <path d="M12 8v8M8 12h8" />
    </>
  ),
  clothing: (
    <path d="M9 4 4.5 6.5l1.5 4 2-1V20h8V9.5l2 1 1.5-4L15 4c-.5 1.5-1.5 2.5-3 2.5S9.5 5.5 9 4z" />
  ),
  footwear: <path d="M3 17.5V8.5h5l1.5 3c2 .8 5.5 1.5 8.5 2.2 1.7.4 3 1.5 3 3.8zM3 17.5h18" />,
  pets: (
    <>
      <circle cx="7" cy="9.5" r="1.8" />
      <circle cx="10.5" cy="6" r="1.8" />
      <circle cx="14.5" cy="6" r="1.8" />
      <circle cx="17.5" cy="9.5" r="1.8" />
      <path d="M8 17c0-3 2-5 4.5-5s4.5 2 4.5 5c0 2-2 2.5-4.5 2.5S8 19 8 17z" />
    </>
  ),
  stationery: <path d="M15.5 4.5 19.5 8.5 9 19H5v-4zM13 7l4 4" />,
  accessories: (
    <>
      <path d="M5 9h14l-1 11H6z" />
      <path d="M9 9V7a3 3 0 0 1 6 0v2" />
    </>
  ),
  box: (
    <>
      <path d="M4 8 12 4l8 4v8l-8 4-8-4z" />
      <path d="M4 8l8 4 8-4M12 12v8" />
    </>
  ),
}

export function CategoryIcon({ name, className }: { name: CategoryIconName; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      focusable="false"
      aria-hidden="true"
    >
      {SHAPES[name]}
    </svg>
  )
}

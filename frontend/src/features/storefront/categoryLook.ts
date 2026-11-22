export const LOW_STOCK = 5

export type CategoryIconName =
  | 'electronics'
  | 'sports'
  | 'home'
  | 'kitchen'
  | 'gift'
  | 'book'
  | 'outdoors'
  | 'beauty'
  | 'games'
  | 'food'
  | 'tools'
  | 'health'
  | 'clothing'
  | 'footwear'
  | 'pets'
  | 'stationery'
  | 'accessories'
  | 'box'

export type CategoryLook = { tone: number; tint: string; ink: string; icon: CategoryIconName }

const PALETTE: { tint: string; ink: string }[] = [
  { tint: '#e3efe6', ink: '#2f6b47' },
  { tint: '#e1ebf5', ink: '#2c5a8c' },
  { tint: '#fbe9dc', ink: '#9a4d24' },
  { tint: '#efe3f0', ink: '#7a3b7e' },
  { tint: '#ddf0ef', ink: '#1f6e6a' },
  { tint: '#f3ecd9', ink: '#76601f' },
  { tint: '#f8e1e4', ink: '#9c3a4b' },
  { tint: '#e6e8ee', ink: '#48506a' },
]

const ICONS: [string[], CategoryIconName][] = [
  [['electronic', 'audio', 'computer', 'phone'], 'electronics'],
  [['sport', 'fitness'], 'sports'],
  [['home', 'office', 'furniture'], 'home'],
  [['kitchen', 'cook'], 'kitchen'],
  [['gift'], 'gift'],
  [['book'], 'book'],
  [['outdoor', 'camping', 'garden'], 'outdoors'],
  [['beauty', 'cosmetic', 'care'], 'beauty'],
  [['game', 'toy'], 'games'],
  [['food', 'beverage', 'drink', 'grocer'], 'food'],
  [['tool', 'hardware'], 'tools'],
  [['health', 'pharma'], 'health'],
  [['footwear', 'shoe'], 'footwear'],
  [['cloth', 'apparel', 'fashion'], 'clothing'],
  [['pet'], 'pets'],
  [['stationer', 'paper', 'school'], 'stationery'],
  [['accessor', 'bag', 'jewel'], 'accessories'],
]

function normalised(category: string): string {
  return category.trim().toLowerCase()
}

function hashOf(text: string): number {
  let hash = 0
  for (const character of text) {
    hash = (hash * 31 + (character.codePointAt(0) ?? 0)) >>> 0
  }
  return hash
}

const TONES: Partial<Record<CategoryIconName, number>> = {
  sports: 0,
  accessories: 0,
  electronics: 1,
  stationery: 1,
  kitchen: 2,
  food: 2,
  pets: 2,
  gift: 3,
  games: 3,
  outdoors: 4,
  health: 4,
  home: 5,
  footwear: 5,
  book: 6,
  beauty: 6,
  clothing: 6,
  tools: 7,
}

export function categoryLook(category: string): CategoryLook {
  const key = normalised(category)
  const icon = ICONS.find(([words]) => words.some((word) => key.includes(word)))?.[1] ?? 'box'
  const tone = TONES[icon] ?? hashOf(key) % PALETTE.length
  return { tone, ...PALETTE[tone], icon }
}

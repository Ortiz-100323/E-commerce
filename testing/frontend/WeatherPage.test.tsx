import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { WeatherPage } from '../../frontend/src/features/weather/WeatherPage'

type Route = { method: string; path: string; status: number; body: unknown }

const lisbon = {
  id: '1',
  city: 'Lisbon',
  location_name: 'Lisbon',
  country: 'Portugal',
  latitude: 38.71667,
  longitude: -9.13333,
  temperature_c: 21.4,
  wind_speed_kmh: 12.6,
  weather_code: 0,
  searched_at: '2026-11-21T12:00:00Z',
}

const porto = { ...lisbon, id: '2', city: 'Porto', location_name: 'Porto', temperature_c: 17.2 }

function stubApi(routes: Route[]) {
  const remaining = [...routes]
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const method = init?.method ?? 'GET'
    const path = String(input)
    const index = remaining.findIndex((route) => route.method === method && route.path === path)
    if (index === -1) {
      throw new Error(`Unexpected request ${method} ${path}`)
    }
    const [route] = remaining.splice(index, 1)
    return new Response(JSON.stringify(route.body), {
      status: route.status,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const HISTORY = '/api/v1/weather/searches?limit=10'
const SEARCH = '/api/v1/weather/searches'

describe('WeatherPage', () => {
  it('shows the search history when it opens', async () => {
    stubApi([{ method: 'GET', path: HISTORY, status: 200, body: [porto, lisbon] }])

    render(<WeatherPage />)

    const history = await screen.findByRole('list', { name: 'Recent searches' })
    const items = within(history).getAllByRole('listitem')
    expect(items.map((item) => item.textContent)).toEqual([
      expect.stringContaining('Porto, Portugal'),
      expect.stringContaining('Lisbon, Portugal'),
    ])
  })

  it('says when there are no searches yet', async () => {
    stubApi([{ method: 'GET', path: HISTORY, status: 200, body: [] }])

    render(<WeatherPage />)

    expect(await screen.findByText('No searches yet.')).toBeInTheDocument()
  })

  it('searches a city, shows the result and refreshes the history', async () => {
    const fetchMock = stubApi([
      { method: 'GET', path: HISTORY, status: 200, body: [] },
      { method: 'POST', path: SEARCH, status: 201, body: lisbon },
      { method: 'GET', path: HISTORY, status: 200, body: [lisbon] },
    ])
    render(<WeatherPage />)
    await screen.findByText('No searches yet.')

    await userEvent.type(screen.getByLabelText('City'), 'Lisbon')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))

    const result = await screen.findByRole('region', { name: 'Current weather' })
    expect(within(result).getByText('Lisbon, Portugal')).toBeInTheDocument()
    expect(within(result).getByText('21.4 °C')).toBeInTheDocument()
    expect(within(result).getByText('Wind 12.6 km/h')).toBeInTheDocument()
    const history = await screen.findByRole('list', { name: 'Recent searches' })
    expect(within(history).getAllByRole('listitem')).toHaveLength(1)
    const postCall = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')
    expect(JSON.parse(String(postCall?.[1]?.body))).toEqual({ city: 'Lisbon' })
  })

  it('explains when the city is not found', async () => {
    stubApi([
      { method: 'GET', path: HISTORY, status: 200, body: [] },
      { method: 'POST', path: SEARCH, status: 404, body: { detail: 'City not found.' } },
    ])
    render(<WeatherPage />)
    await screen.findByText('No searches yet.')

    await userEvent.type(screen.getByLabelText('City'), 'Atlantis')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('City not found')
    expect(screen.queryByRole('region', { name: 'Current weather' })).not.toBeInTheDocument()
  })

  it('explains when the weather service is unavailable', async () => {
    stubApi([
      { method: 'GET', path: HISTORY, status: 200, body: [] },
      { method: 'POST', path: SEARCH, status: 502, body: { detail: 'down' } },
    ])
    render(<WeatherPage />)
    await screen.findByText('No searches yet.')

    await userEvent.type(screen.getByLabelText('City'), 'Lisbon')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('weather service is unavailable')
  })

  it('keeps the search button disabled until a city is typed', async () => {
    stubApi([{ method: 'GET', path: HISTORY, status: 200, body: [] }])
    render(<WeatherPage />)
    await screen.findByText('No searches yet.')

    expect(screen.getByRole('button', { name: 'Search' })).toBeDisabled()
    await userEvent.type(screen.getByLabelText('City'), '   ')
    expect(screen.getByRole('button', { name: 'Search' })).toBeDisabled()
  })
})

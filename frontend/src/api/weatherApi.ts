export type WeatherSearch = {
  id: string
  city: string
  location_name: string
  country: string
  latitude: number
  longitude: number
  temperature_c: number
  wind_speed_kmh: number
  weather_code: number
  searched_at: string
}

export class WeatherApiError extends Error {
  readonly status: number

  constructor(status: number) {
    super(`Request failed with status ${status}`)
    this.status = status
  }
}

const SEARCHES_PATH = '/api/v1/weather/searches'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
  })
  if (!response.ok) {
    throw new WeatherApiError(response.status)
  }
  return (await response.json()) as T
}

export function searchWeather(city: string): Promise<WeatherSearch> {
  return request<WeatherSearch>(SEARCHES_PATH, { method: 'POST', body: JSON.stringify({ city }) })
}

export function listWeatherSearches(limit = 10): Promise<WeatherSearch[]> {
  return request<WeatherSearch[]>(`${SEARCHES_PATH}?limit=${limit}`)
}

import { useCallback, useEffect, useState, type FormEvent } from 'react'

import {
  listWeatherSearches,
  searchWeather,
  WeatherApiError,
  type WeatherSearch,
} from '../../api/weatherApi'
import styles from './WeatherPage.module.css'

function errorMessage(error: unknown): string {
  if (error instanceof WeatherApiError && error.status === 404) {
    return 'City not found. Check the spelling and try again.'
  }
  if (error instanceof WeatherApiError && error.status === 422) {
    return 'Type a city name of up to 100 characters.'
  }
  return 'The weather service is unavailable. Try again later.'
}

function place(search: WeatherSearch): string {
  return search.country ? `${search.location_name}, ${search.country}` : search.location_name
}

export function WeatherPage() {
  const [city, setCity] = useState('')
  const [result, setResult] = useState<WeatherSearch | null>(null)
  const [history, setHistory] = useState<WeatherSearch[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const refreshHistory = useCallback(async () => {
    try {
      setHistory(await listWeatherSearches())
    } catch {
      setHistory([])
    }
  }, [])

  useEffect(() => {
    void refreshHistory()
  }, [refreshHistory])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoading(true)
    setError(null)
    try {
      setResult(await searchWeather(city.trim()))
      await refreshHistory()
    } catch (caught) {
      setResult(null)
      setError(errorMessage(caught))
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className={styles.page}>
      <header>
        <h1>Weather check</h1>
        <p className={styles.note}>Temporary test feature (ECOM-000). It proves the stack works end to end.</p>
      </header>

      <form className={styles.form} onSubmit={handleSubmit}>
        <label htmlFor="city">City</label>
        <input
          id="city"
          value={city}
          onChange={(event) => setCity(event.target.value)}
          placeholder="Lisbon"
          maxLength={100}
          autoComplete="off"
        />
        <button type="submit" disabled={loading || city.trim() === ''}>
          {loading ? 'Searching…' : 'Search'}
        </button>
      </form>

      {error && (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      )}

      {result && (
        <section aria-label="Current weather" className={styles.result}>
          <h2>{place(result)}</h2>
          <p className={styles.temperature}>{`${result.temperature_c} °C`}</p>
          <p>{`Wind ${result.wind_speed_kmh} km/h`}</p>
        </section>
      )}

      <section className={styles.history}>
        <h2 id="history-heading">Recent searches</h2>
        {history !== null && history.length === 0 && <p>No searches yet.</p>}
        {history !== null && history.length > 0 && (
          <ul aria-labelledby="history-heading">
            {history.map((search) => (
              <li key={search.id}>
                <span>{place(search)}</span>
                <span>{`${search.temperature_c} °C`}</span>
                <time dateTime={search.searched_at}>
                  {new Date(search.searched_at).toLocaleString()}
                </time>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  )
}

let errorsExpected = false

export function expectErrorNotifications(): void {
  errorsExpected = true
}

export function takeErrorExpectation(): boolean {
  const expected = errorsExpected
  errorsExpected = false
  return expected
}

export function errorNotificationsOnPage(): string[] {
  return [...document.querySelectorAll('[aria-label="Notifications"] [role="alert"]')].map(
    (notice) => notice.textContent ?? '',
  )
}

export function pageShowsUnexpectedError(): boolean {
  return (document.body.textContent ?? '').includes('Something unexpected went wrong')
}

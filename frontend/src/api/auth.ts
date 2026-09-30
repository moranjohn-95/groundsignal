export interface CurrentUser {
  id: number
  email: string
  is_active: boolean
  created_at: string
}

export class AuthApiError extends Error {
  constructor(public readonly status: number) {
    super(`Account request failed with status ${status}.`)
    this.name = 'AuthApiError'
  }
}

export async function fetchCurrentUser(): Promise<CurrentUser | null> {
  const response = await fetch('/api/v1/auth/me', {
    credentials: 'same-origin',
  })
  if (response.status === 401) return null
  if (!response.ok) throw new AuthApiError(response.status)
  return (await response.json()) as CurrentUser
}

export async function submitAccount(
  action: 'signup' | 'login',
  email: string,
  password: string,
): Promise<CurrentUser> {
  const response = await fetch(`/api/v1/auth/${action}`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!response.ok) throw new AuthApiError(response.status)
  return (await response.json()) as CurrentUser
}

export async function logoutAccount(): Promise<void> {
  const response = await fetch('/api/v1/auth/logout', {
    method: 'POST',
    credentials: 'same-origin',
  })
  if (!response.ok) throw new AuthApiError(response.status)
}

import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type MouseEventHandler,
} from 'react'

import { AuthApiError, submitAccount, type CurrentUser } from '../../api/auth'
import { saveReturnSearch, type SaveReturn } from './saveReturn'

interface AccountPageProps {
  mode: 'signup' | 'login'
  currentUser: CurrentUser | null
  onAuthenticated: (user: CurrentUser) => Promise<void> | void
  onNavigate: MouseEventHandler<HTMLAnchorElement>
  saveReturn?: SaveReturn | null
}

function errorMessage(error: unknown, mode: 'signup' | 'login'): string {
  if (error instanceof AuthApiError) {
    if (error.status === 409 && mode === 'signup') {
      return 'An account with this email already exists. Log in instead.'
    }
    if (error.status === 401 && mode === 'login') {
      return 'Email or password is incorrect.'
    }
    if (error.status === 422) {
      return 'Check your email and password, then try again.'
    }
    if (error.status === 429) {
      return 'Too many attempts. Please wait and try again.'
    }
    if (error.status === 403) {
      return 'The request was blocked. Reload the page and try again.'
    }
  }
  return 'The account service is unavailable right now. Please try again.'
}

export default function AccountPage({
  mode,
  currentUser,
  onAuthenticated,
  onNavigate,
  saveReturn,
}: AccountPageProps) {
  const headingRef = useRef<HTMLHeadingElement>(null)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  useEffect(() => {
    headingRef.current?.focus()
  }, [])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (pending) return
    setError(null)
    if (mode === 'signup' && password !== confirmation) {
      setError('Passwords do not match.')
      return
    }
    setPending(true)
    try {
      const user = await submitAccount(mode, email.trim(), password)
      await onAuthenticated(user)
    } catch (reason: unknown) {
      setError(errorMessage(reason, mode))
    } finally {
      setPending(false)
    }
  }

  const title = mode === 'signup' ? 'Create your account' : 'Log in'
  const returnQuery = saveReturn ? saveReturnSearch(saveReturn.opportunityId) : ''

  return (
    <section className="account-page" aria-labelledby="account-heading">
      <a className="account-page__back" href={saveReturn?.path ?? '/'} onClick={onNavigate}>
        {saveReturn ? 'Back to opportunity' : 'Back to opportunities'}
      </a>
      <div className="account-card">
        <h2 id="account-heading" ref={headingRef} tabIndex={-1}>
          {title}
        </h2>
        {currentUser ? (
          <p className="account-card__intro">
            You are signed in as {currentUser.email}. Return to opportunities to
            continue your search.
          </p>
        ) : (
          <>
            <p className="account-card__intro">
              {mode === 'signup'
                ? 'Create a free account to get started.'
                : 'Welcome back to SiteForecaster.'}
            </p>
            <form className="account-form" onSubmit={(event) => void handleSubmit(event)}>
              <div className="form-field">
                <label htmlFor="account-email">Email address</label>
                <input
                  id="account-email"
                  type="email"
                  name="email"
                  autoComplete="username"
                  required
                  maxLength={320}
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  disabled={pending}
                />
              </div>
              <div className="form-field">
                <label htmlFor="account-password">Password</label>
                <input
                  id="account-password"
                  type="password"
                  name="password"
                  autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                  required
                  minLength={mode === 'signup' ? 12 : 1}
                  maxLength={1024}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  disabled={pending}
                />
              </div>
              {mode === 'signup' && (
                <div className="form-field">
                  <label htmlFor="account-confirmation">Confirm password</label>
                  <input
                    id="account-confirmation"
                    type="password"
                    name="confirmation"
                    autoComplete="new-password"
                    required
                    minLength={12}
                    maxLength={1024}
                    value={confirmation}
                    onChange={(event) => setConfirmation(event.target.value)}
                    disabled={pending}
                  />
                </div>
              )}
              {error && <p className="account-form__error" role="alert">{error}</p>}
              <button className="button button--primary" type="submit" disabled={pending}>
                {pending ? 'Please wait…' : mode === 'signup' ? 'Create account' : 'Log in'}
              </button>
            </form>
            <p className="account-card__switch">
              {mode === 'signup' ? 'Already have an account?' : 'New to SiteForecaster?'}{' '}
              <a href={`${mode === 'signup' ? '/login' : '/signup'}${returnQuery}`} onClick={onNavigate}>
                {mode === 'signup' ? 'Log in' : 'Create an account'}
              </a>
            </p>
          </>
        )}
      </div>
    </section>
  )
}

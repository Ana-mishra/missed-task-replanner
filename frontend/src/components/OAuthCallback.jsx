import { useEffect, useState } from 'react'
import { setAccessToken } from '../services/api.js'

function OAuthCallback({ onAuthenticated }) {
  const [error, setError] = useState(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const token = params.get('token')
    const oauthError = params.get('error')

    // Remove the token (and any OAuth params) from the URL immediately
    // so it never sits in browser history or is visible in the address bar.
    window.history.replaceState({}, document.title, window.location.pathname)

    if (oauthError) {
      const messages = {
        access_denied: 'You cancelled the sign-in. Please try again.',
        invalid_state: 'The sign-in request expired or was tampered with. Please try again.',
        provider_error: 'The sign-in provider returned an error. Please try again.',
        missing_code_or_state: 'The sign-in response was incomplete. Please try again.',
      }
      setError(messages[oauthError] || 'Sign-in failed. Please try again.')
      return
    }

    if (!token) {
      setError('No authentication token was received. Please try signing in again.')
      return
    }

    try {
      setAccessToken(token)
    } catch {
      setError('Could not save your session. Please allow local storage and try again.')
      return
    }

    onAuthenticated()
  }, [])

  if (error) {
    return (
      <main className="auth-page">
        <section className="auth-page__panel" style={{ gridColumn: '1 / -1' }} aria-labelledby="oauth-error-heading">
          <div className="auth-card">
            <p className="auth-card__eyebrow">Sign-in failed</p>
            <h2 id="oauth-error-heading">Something went wrong</h2>
            <p className="auth-card__error" role="alert">{error}</p>
            <button
              className="auth-submit"
              type="button"
              onClick={() => window.location.replace('/')}
            >
              Back to sign in
            </button>
          </div>
        </section>
      </main>
    )
  }

  return (
    <main className="auth-page">
      <section className="auth-page__panel" style={{ gridColumn: '1 / -1' }} aria-label="Signing in">
        <div className="auth-card">
          <p className="auth-card__eyebrow">Just a moment</p>
          <h2>Signing you in…</h2>
        </div>
      </section>
    </main>
  )
}

export default OAuthCallback

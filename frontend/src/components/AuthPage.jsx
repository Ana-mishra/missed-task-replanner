import { useState } from 'react'

import { login, register } from '../services/api.js'

function AuthPage({ onAuthenticated }) {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const isRegistering = mode === 'register'

  function switchMode(nextMode) {
    setMode(nextMode)
    setError(null)
    setConfirmPassword('')
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)

    if (isRegistering && password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    setSubmitting(true)
    try {
      if (isRegistering) {
        const displayName = email.trim().split('@')[0] || 'Planora user'
        await register({ name: displayName, email, password })
      }

      await login({ email, password })
      onAuthenticated()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-page__intro" aria-label="About Planora">
        <div className="auth-brand">
          <span className="auth-brand__mark" aria-hidden="true">P</span>
          <div>
            <strong>Planora</strong>
            <span>Your day, your way</span>
          </div>
        </div>

        <div className="auth-page__message">
          <p className="auth-page__eyebrow">A gentler way forward</p>
          <h1>Plan gently.<br />Recover kindly.</h1>
          <p>
            Miss a task? No worries. Planora helps you get back on track with
            compassion and clarity.
          </p>
        </div>

        <p className="auth-page__note">
          <span aria-hidden="true">🌿</span>
          Progress is not about perfection. It is about showing up for yourself.
        </p>
      </section>

      <section className="auth-page__panel" aria-labelledby="auth-heading">
        <div className="auth-page__switch">
          <span>{isRegistering ? 'Already with Planora?' : 'New to Planora?'}</span>
          <button type="button" onClick={() => switchMode(isRegistering ? 'login' : 'register')}>
            {isRegistering ? 'Log in' : 'Create an account'}
          </button>
        </div>

        <form className="auth-card" onSubmit={handleSubmit}>
          <p className="auth-card__eyebrow">Your gentle reset</p>
          <h2 id="auth-heading">{isRegistering ? 'Create your account' : 'Welcome back!'}</h2>
          <p className="auth-card__copy">
            {isRegistering
              ? 'Start planning your days with more clarity and care.'
              : 'Log in to continue your journey.'}
          </p>

          <label className="auth-field">
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              required
            />
          </label>

          <label className="auth-field">
            <span>Password</span>
            <span className="auth-password-field">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter your password"
                autoComplete={isRegistering ? 'new-password' : 'current-password'}
                minLength="8"
                required
              />
              <button
                type="button"
                className="auth-password-toggle"
                onClick={() => setShowPassword((visible) => !visible)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </span>
          </label>

          {isRegistering && (
            <label className="auth-field">
              <span>Confirm password</span>
              <input
                type={showPassword ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                placeholder="Repeat your password"
                autoComplete="new-password"
                minLength="8"
                required
              />
            </label>
          )}

          {error && <p className="auth-card__error" role="alert">{error}</p>}

          <button className="auth-submit" type="submit" disabled={submitting}>
            {submitting
              ? isRegistering ? 'Creating account…' : 'Logging in…'
              : isRegistering ? 'Create account' : 'Log in'}
          </button>
        </form>
      </section>
    </main>
  )
}

export default AuthPage

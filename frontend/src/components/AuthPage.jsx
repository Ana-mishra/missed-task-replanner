import { useEffect, useState } from 'react'

import { login, oauthLoginUrl, register, requestPasswordReset, resetPassword } from '../services/api.js'
import { IconGitHub, IconGoogle } from './icons.jsx'

const RESEND_COOLDOWN_SECONDS = 60

function AuthPage({ onAuthenticated, initialMode = 'login', onBack, onForgotPassword, onBackToLogin, resetToken }) {
  const [mode, setMode] = useState(initialMode)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [resetEmailSent, setResetEmailSent] = useState(false)
  const [oauthProvider, setOauthProvider] = useState(null)
  const [resendCooldown, setResendCooldown] = useState(0)
  const [newPassword, setNewPassword] = useState('')
  const [confirmNewPassword, setConfirmNewPassword] = useState('')
  const [resetDone, setResetDone] = useState(false)

  const isRegistering = mode === 'register'
  const isForgot = mode === 'forgot'
  const isReset = mode === 'reset'
  const goBackToLogin = onBackToLogin || onBack

  useEffect(() => {
    if (resendCooldown <= 0) return undefined
    const timer = window.setTimeout(() => setResendCooldown((value) => value - 1), 1000)
    return () => window.clearTimeout(timer)
  }, [resendCooldown])

  function switchMode(nextMode) {
  setMode(nextMode)
  setError(null)
  setConfirmPassword('')
  setName('')
}

  async function handleForgotSubmit(event) {
    event.preventDefault()
    setError(null)
    setOauthProvider(null)
    setSubmitting(true)
    try {
      const result = await requestPasswordReset(email.trim())
      if (result && (result.provider === 'google' || result.provider === 'github')) {
        setOauthProvider(result.provider)
      }
      setResetEmailSent(true)
      setResendCooldown(RESEND_COOLDOWN_SECONDS)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSubmitting(false)
    }
  }

  const OAUTH_PROVIDER_LABELS = { google: 'Google', github: 'GitHub' }
  const OauthProviderIcon = oauthProvider === 'github' ? IconGitHub : IconGoogle

  async function handleResetSubmit(event) {
    event.preventDefault()
    setError(null)

    if (!newPassword) {
      setError('Please enter a new password.')
      return
    }

    if (newPassword !== confirmNewPassword) {
      setError('Passwords do not match.')
      return
    }

    setSubmitting(true)
    try {
      await resetPassword({ token: resetToken, password: newPassword, passwordConfirm: confirmNewPassword })
      setResetDone(true)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSubmitting(false)
    }
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
  await register({
    name: name.trim(),
    email,
    password,
  })
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
        {onBack && (
          <button type="button" className="auth-page__back" onClick={onBack}>
            ← Back to Planora
          </button>
        )}
        <div className="auth-page__switch">
          <span>{isRegistering ? 'Already with Planora?' : 'New to Planora?'}</span>
          <button type="button" onClick={() => switchMode(isRegistering ? 'login' : 'register')}>
            {isRegistering ? 'Log in' : 'Create an account'}
          </button>
        </div>

        {isForgot ? (
          <form className="auth-card" onSubmit={handleForgotSubmit}>
            <p className="auth-card__eyebrow">Your gentle reset</p>
            {resetEmailSent ? (
              oauthProvider ? (
                <>
                  <h2 id="auth-heading">Your account uses {OAUTH_PROVIDER_LABELS[oauthProvider]} sign-in.</h2>
                  <p className="auth-card__copy">You created your Planora account with {OAUTH_PROVIDER_LABELS[oauthProvider]}, so there isn&rsquo;t a Planora password to reset.</p>
                  {error && <p className="auth-card__error" role="alert">{error}</p>}
                  <button
                    type="button"
                    className="auth-oauth-button"
                    onClick={() => { window.location.href = oauthLoginUrl(oauthProvider); }}
                  >
                    <span className="auth-oauth-button__icon" aria-hidden="true"><OauthProviderIcon /></span>
                    Continue with {OAUTH_PROVIDER_LABELS[oauthProvider]}
                  </button>
                </>
              ) : (
                <>
                  <h2 id="auth-heading">Check your email</h2>
                  <p className="auth-card__copy">If an account exists for that email, we&rsquo;ve sent you a password reset link.</p>
                  {error && <p className="auth-card__error" role="alert">{error}</p>}
                  <button className="auth-submit" type="submit" disabled={submitting || resendCooldown > 0}>
                    {resendCooldown > 0 ? `Resend email in ${resendCooldown}s` : submitting ? 'Sending…' : 'Resend email'}
                  </button>
                </>
              )
            ) : (
              <>
                <h2 id="auth-heading">Forgot your password?</h2>
                <p className="auth-card__copy">Enter the email address associated with your Planora account and we&rsquo;ll send you a link to reset it.</p>
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
                {error && <p className="auth-card__error" role="alert">{error}</p>}
                <button className="auth-submit" type="submit" disabled={submitting}>
                  {submitting ? 'Sending…' : 'Send reset link'}
                </button>
              </>
            )}
            {goBackToLogin && (
              <button type="button" className="auth-back-login" onClick={goBackToLogin}>
                ← Back to login
              </button>
            )}
          </form>
        ) : isReset ? (
          <form className="auth-card" onSubmit={handleResetSubmit}>
            <p className="auth-card__eyebrow">Your gentle reset</p>
            {!resetToken ? (
              <>
                <h2 id="auth-heading">Reset link invalid</h2>
                <p className="auth-card__error" role="alert">This password reset link is invalid or has expired. Please request a new one.</p>
              </>
            ) : resetDone ? (
              <>
                <h2 id="auth-heading">Password updated</h2>
                <p className="auth-card__copy">Your password has been changed successfully.</p>
                <button className="auth-submit" type="button" onClick={goBackToLogin}>
                  Log in
                </button>
              </>
            ) : (
              <>
                <h2 id="auth-heading">Reset your password</h2>
                <p className="auth-card__copy">Choose a new password for your Planora account.</p>
                <label className="auth-field">
                  <span>New password</span>
                  <span className="auth-password-field">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={newPassword}
                      onChange={(event) => setNewPassword(event.target.value)}
                      placeholder="Enter a new password"
                      autoComplete="new-password"
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
                <label className="auth-field">
                  <span>Confirm new password</span>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={confirmNewPassword}
                    onChange={(event) => setConfirmNewPassword(event.target.value)}
                    placeholder="Repeat the new password"
                    autoComplete="new-password"
                    minLength="8"
                    required
                  />
                </label>
                {error && <p className="auth-card__error" role="alert">{error}</p>}
                <button className="auth-submit" type="submit" disabled={submitting}>
                  {submitting ? 'Resetting…' : 'Reset password'}
                </button>
              </>
            )}
            {goBackToLogin && !resetDone && (
              <button type="button" className="auth-back-login" onClick={goBackToLogin}>
                ← Back to login
              </button>
            )}
          </form>
        ) : (
        <form className="auth-card" onSubmit={handleSubmit}>
          <p className="auth-card__eyebrow">Your gentle reset</p>
          <h2 id="auth-heading">{isRegistering ? 'Create your account' : 'Welcome back!'}</h2>
          {isRegistering && (
  <label className="auth-field">
    <span>What should we call you?</span>
    <input
      type="text"
      value={name}
      onChange={(event) => setName(event.target.value)}
      placeholder="Your name"
      autoComplete="name"
      maxLength="100"
      required
    />
  </label>
)}

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

          {!isRegistering && onForgotPassword && (
            <div className="auth-forgot-row">
              <button type="button" className="auth-forgot-link" onClick={onForgotPassword}>
                Forgot password?
              </button>
            </div>
          )}

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

          <div className="auth-divider">
            <span>or continue with</span>
          </div>

          <button
            type="button"
            className="auth-oauth-button"
            onClick={() => { window.location.href = oauthLoginUrl('google'); }}
          >
            <span className="auth-oauth-button__icon" aria-hidden="true"><IconGoogle /></span>
            Continue with Google
          </button>

          <button
            type="button"
            className="auth-oauth-button"
            onClick={() => { window.location.href = oauthLoginUrl('github'); }}
          >
            <span className="auth-oauth-button__icon" aria-hidden="true"><IconGitHub /></span>
            Continue with GitHub
          </button>
        </form>
        )}
      </section>
    </main>
  )
}

export default AuthPage

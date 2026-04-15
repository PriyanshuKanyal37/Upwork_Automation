import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiRequestError, login, register } from '../lib/api'
import { markSessionHint, hasSessionHint } from '../lib/session'

type AuthMode = 'login' | 'register'

export function AuthenticationPage() {
  const navigate = useNavigate()
  const [mode,        setMode]        = useState<AuthMode>('login')
  const [displayName, setDisplayName] = useState('')
  const [email,       setEmail]       = useState('')
  const [password,    setPassword]    = useState('')
  const [showPwd,     setShowPwd]     = useState(false)
  const [busy,        setBusy]        = useState(false)
  const [error,       setError]       = useState<string | null>(null)

  useEffect(() => {
    if (hasSessionHint()) {
      markSessionHint()
      navigate('/workspace', { replace: true })
    }
  }, [navigate])

  const canSubmit = useMemo(() => {
    if (mode === 'register' && displayName.trim().length < 2) return false
    return email.trim().length > 3 && password.trim().length >= 8
  }, [displayName, email, mode, password])

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (!canSubmit) return
    setBusy(true)
    setError(null)
    try {
      const res =
        mode === 'register'
          ? await register({ display_name: displayName.trim(), email: email.trim(), password })
          : await login({ email: email.trim(), password })
      markSessionHint()
      navigate(mode === 'register' ? '/onboarding' : '/workspace')
      void res
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Unexpected error. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className="app-bg"
      style={{ minHeight: '100svh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px 20px' }}
    >
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(0,1fr)',
        gap: 40,
        width: '100%',
        maxWidth: 1100,
        alignItems: 'center',
      }}>

        {/* Hero copy */}
        <div style={{ maxWidth: 560, margin: '0 auto' }}>
          <p className="page-eyebrow">Ladder / Jobs</p>
          <h1 className="page-title" style={{ marginTop: 10, fontSize: 'clamp(2rem,5vw,3.5rem)' }}>
            One clean thread for every Upwork job.
          </h1>
          <p className="page-subtitle" style={{ marginTop: 12, maxWidth: 460 }}>
            Paste a job URL, let the AI extract and generate, revise step by step, then publish to your connected tools.
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 24 }}>
            {['Intake', 'Extraction', 'Generation', 'Revision', 'Publish'].map((lbl) => (
              <span key={lbl} className="chip">{lbl}</span>
            ))}
          </div>
        </div>

        {/* Auth card */}
        <div
          className="card-elevated"
          style={{ padding: 28, maxWidth: 420, width: '100%', margin: '0 auto' }}
        >
          {/* Mode tabs */}
          <div className="tab-bar" style={{ marginBottom: 24 }}>
            <button
              type="button"
              className={`tab-btn${mode === 'login' ? ' active' : ''}`}
              style={{ flex: 1 }}
              onClick={() => { setMode('login'); setError(null) }}
            >
              Login
            </button>
            <button
              type="button"
              className={`tab-btn${mode === 'register' ? ' active' : ''}`}
              style={{ flex: 1 }}
              onClick={() => { setMode('register'); setError(null) }}
            >
              Register
            </button>
          </div>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {mode === 'register' && (
              <input
                className="input"
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Display name"
                autoComplete="name"
              />
            )}
            <input
              className="input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email"
              autoComplete="email"
            />
            <div style={{ position: 'relative' }}>
              <input
                className="input"
                type={showPwd ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password (8+ characters)"
                autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
                style={{ paddingRight: 44 }}
              />
              <button
                type="button"
                onClick={() => setShowPwd((v) => !v)}
                tabIndex={-1}
                style={{
                  position: 'absolute', right: 12, top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: showPwd ? 'var(--primary)' : 'var(--on-surface-muted)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  padding: 4, borderRadius: 4,
                  transition: 'color 150ms',
                }}
                aria-label={showPwd ? 'Hide password' : 'Show password'}
              >
                {showPwd ? (
                  /* Eye-off icon */
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94"/>
                    <path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19"/>
                    <line x1="1" y1="1" x2="23" y2="23"/>
                  </svg>
                ) : (
                  /* Eye icon */
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                    <circle cx="12" cy="12" r="3"/>
                  </svg>
                )}
              </button>
            </div>

            {error && (
              <div className="banner banner-error">{error}</div>
            )}

            <button
              type="submit"
              className="btn btn-primary btn-full btn-pill btn-lg"
              disabled={!canSubmit || busy}
              style={{ marginTop: 4 }}
            >
              {busy ? 'Please wait…' : mode === 'register' ? 'Create account' : 'Continue →'}
            </button>
          </form>

          <p style={{ marginTop: 20, textAlign: 'center', fontSize: '0.75rem', color: 'var(--on-surface-muted)' }}>
            {mode === 'login'
              ? "Don't have an account? "
              : 'Already have an account? '}
            <button
              type="button"
              onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(null) }}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--primary)', fontWeight: 600, fontSize: 'inherit' }}
            >
              {mode === 'login' ? 'Register' : 'Login'}
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}




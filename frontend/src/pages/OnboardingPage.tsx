import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ApiRequestError,
  beautifyManualProfile,
  createProfile,
  extractUpworkProfile,
  getProfile,
} from '../lib/api'
import { clearSessionHint, hasProfileHint, markProfileHint, markSessionHint } from '../lib/session'

function trimNull(v: string) { const t = v.trim(); return t || null }

/* ════════════════════════════════════════════
   Modal Editor (Cloned from ProfilePage)
════════════════════════════════════════════ */
function ModalEditor({
  title,
  value,
  placeholder,
  onSave,
  onClose,
  onBeautify,
  beautifying,
}: {
  title: string
  value: string
  placeholder: string
  onSave: (v: string) => void
  onClose: () => void
  onBeautify?: (draft: string, setDraft: (v: string) => void) => void
  beautifying?: boolean
}) {
  const [draft, setDraft] = useState(value)
  const wordCount = draft.trim().split(/\s+/).filter(Boolean).length

  useEffect(() => {
    const fn = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', fn)
    return () => window.removeEventListener('keydown', fn)
  }, [onClose])

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 200,
        background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 24,
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="card-elevated"
        style={{
          width: '100%', maxWidth: 760,
          display: 'flex', flexDirection: 'column',
          maxHeight: 'calc(100svh - 48px)',
          overflow: 'hidden',
        }}
      >
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 20px',
          borderBottom: beautifying ? 'none' : '1px solid var(--border)',
          flexShrink: 0,
          flexWrap: 'wrap',
          gap: 10,
        }}>
          <p className="section-label" style={{ fontSize: '0.7rem' }}>{title}</p>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            {onBeautify && (
              <button
                type="button"
                disabled={beautifying || draft.trim().length < 20}
                onClick={() => onBeautify(draft, setDraft)}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 5,
                  height: 28, padding: '0 12px', borderRadius: 999,
                  fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.04em',
                  background: beautifying ? 'rgba(74,222,128,0.06)' : 'rgba(74,222,128,0.12)',
                  border: '1px solid var(--border-accent)', color: 'var(--primary)',
                  cursor: beautifying ? 'wait' : 'pointer',
                  transition: 'background 150ms, opacity 150ms',
                  opacity: draft.trim().length < 20 ? 0.45 : 1,
                  whiteSpace: 'nowrap',
                }}
              >
                {beautifying ? 'Beautifying…' : '✦ Beautify by AI'}
              </button>
            )}
            <span style={{ fontSize: '0.72rem', color: 'var(--on-surface-muted)' }}>{wordCount} words</span>
            <button type="button" className="btn btn-sm btn-ghost" onClick={onClose} style={{ borderRadius: 8 }}>Cancel</button>
            <button
              type="button"
              className="btn btn-sm btn-primary"
              onClick={() => { onSave(draft); onClose() }}
              style={{ borderRadius: 8, padding: '0 14px' }}
            >
              Apply
            </button>
          </div>
        </div>
        {beautifying && (
          <div style={{ height: 2, background: 'var(--surface-high)', overflow: 'hidden', flexShrink: 0 }}>
            <div style={{
              height: '100%',
              background: 'linear-gradient(90deg, transparent 0%, var(--primary) 40%, var(--primary) 60%, transparent 100%)',
              animation: 'scanline 1.4s ease-in-out infinite',
              width: '60%',
            }} />
          </div>
        )}
        {!beautifying && <div style={{ height: 1, background: 'var(--border)', flexShrink: 0 }} />}
        <textarea
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={placeholder}
          style={{
            flex: 1, background: 'transparent', border: 'none', outline: 'none',
            color: 'var(--on-surface)', fontSize: '0.875rem', lineHeight: 1.7,
            padding: '20px 24px', resize: 'none', fontFamily: 'Inter, system-ui, sans-serif',
            overflowY: 'auto', minHeight: 320,
          }}
        />
      </div>
    </div>
  )
}

/* ════════════════════════════════════════════
   TextFieldButton (Cloned from ProfilePage)
════════════════════════════════════════════ */
function TextFieldButton({
  label,
  value,
  placeholder,
  modalTitle,
  onChange,
  onBeautify,
  beautifying,
}: {
  label: string
  value: string
  placeholder: string
  modalTitle: string
  onChange: (v: string) => void
  onBeautify?: (draft: string, setDraft: (v: string) => void) => void
  beautifying?: boolean
}) {
  const [open, setOpen] = useState(false)
  const preview = value.trim() ? value.trim().slice(0, 120).replace(/\n+/g, ' ') : ''

  return (
    <>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
        {label && <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--on-surface-muted)' }}>{label}</label>}
        <button
          type="button"
          onClick={() => setOpen(true)}
          style={{
            display: 'flex', alignItems: 'center', gap: 10,
            width: '100%', textAlign: 'left',
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid var(--border)',
            borderRadius: 10,
            padding: '0 14px',
            height: 48,
            cursor: 'pointer',
            transition: 'border-color 150ms, background 150ms',
            fontFamily: 'Inter, system-ui, sans-serif',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = 'var(--border-accent)'
            e.currentTarget.style.background = 'rgba(255,255,255,0.06)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = 'var(--border)'
            e.currentTarget.style.background = 'rgba(255,255,255,0.04)'
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" style={{ flexShrink: 0, color: 'var(--primary)' }}>
            <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
            <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
          </svg>
          <span style={{
            flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            fontSize: '0.8125rem',
            color: preview ? 'var(--on-surface)' : 'var(--on-surface-muted)',
          }}>
            {preview || placeholder}
          </span>
          {value.trim() && (
            <span style={{
              flexShrink: 0, height: 20, padding: '0 8px',
              borderRadius: 999, fontSize: '0.68rem', fontWeight: 600,
              background: 'var(--primary-glow)', color: 'var(--primary)',
              border: '1px solid var(--border-accent)',
              display: 'flex', alignItems: 'center', gap: 4,
            }}>
              {value.trim().split(/\s+/).filter(Boolean).length}w
            </span>
          )}
        </button>
      </div>

      {open && (
        <ModalEditor
          title={modalTitle}
          value={value}
          placeholder={placeholder}
          onSave={onChange}
          onClose={() => setOpen(false)}
          onBeautify={onBeautify}
          beautifying={beautifying}
        />
      )}
    </>
  )
}

/* ════════════════════════════════════════════
   OnboardingPage
════════════════════════════════════════════ */
export function OnboardingPage() {
  const navigate = useNavigate()

  const [busy,       setBusy]       = useState(false)
  const [extracting, setExtracting] = useState(false)
  const [beautifying,setBeautifying]= useState(false)
  const [error,      setError]      = useState<string | null>(null)
  const [success,    setSuccess]    = useState<string | null>(null)

  const [profileUrl,        setProfileUrl]        = useState('')
  const [profileId,         setProfileId]         = useState('')
  const [profileMarkdown,   setProfileMarkdown]   = useState('')
  const [globalInstruction, setGlobalInstruction] = useState('')

  /* Redirection logic: if already onboarded, push to workspace */
  useEffect(() => {
    if (hasProfileHint()) {
      navigate('/workspace', { replace: true })
      return
    }

    let cancelled = false
    void (async () => {
      try {
        const p = await getProfile()
        if (!cancelled && p) {
          markProfileHint()
          navigate('/workspace', { replace: true })
        }
      } catch {
        /* 404 is expected for new users */
      }
    })()

    return () => {
      cancelled = true
    }
  }, [navigate])

  const handleExtract = async () => {
    const url = profileUrl.trim()
    if (!url) return
    setExtracting(true); setError(null); setSuccess(null)
    try {
      const r = await extractUpworkProfile(url)
      const p = r.profile
      setProfileUrl(p.upwork_profile_url ?? url)
      setProfileId(p.upwork_profile_id ?? '')
      setProfileMarkdown(p.upwork_profile_markdown ?? '')
      if (r.extracted) {
        setSuccess(r.message || 'Profile extracted successfully!')
      } else {
        setError(r.message || 'Could not extract full profile markdown. Please paste manually.')
      }
    } catch (e) {
      setError(e instanceof ApiRequestError ? e.message : 'Extraction failed. Please verify the URL or enter details manually.')
    } finally {
      setExtracting(false)
    }
  }

  const handleComplete = async () => {
    if (!profileMarkdown.trim()) {
      setError('Please provide some profile content before continuing.')
      return
    }
    setBusy(true); setError(null); setSuccess(null)
    try {
      await createProfile({
        upwork_profile_url: trimNull(profileUrl),
        upwork_profile_id: trimNull(profileId),
        upwork_profile_markdown: trimNull(profileMarkdown),
        custom_global_instruction: trimNull(globalInstruction),
      })
      markProfileHint()
      markSessionHint()
      navigate('/workspace', { replace: true })
    } catch (e) {
      setError(e instanceof ApiRequestError ? e.message : 'Error saving profile.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app-bg" style={{ minHeight: '100svh', padding: '60px 20px' }}>
      <div style={{ maxWidth: 640, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 32 }}>

        {/* Back to Login */}
        <div style={{ textAlign: 'center' }}>
          <button
            type="button"
            onClick={() => { clearSessionHint(); navigate('/auth', { replace: true }) }}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              background: 'transparent', border: 'none', cursor: 'pointer',
              color: 'var(--on-surface-muted)', fontSize: '0.8rem', fontWeight: 500,
              padding: '4px 8px', borderRadius: 8,
              transition: 'color 150ms',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--primary)' }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--on-surface-muted)' }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5M12 5l-7 7 7 7" />
            </svg>
            Back to Login
          </button>
        </div>

        {/* Header */}
        <div style={{ textAlign: 'center' }}>
          <p className="page-eyebrow">Onboarding</p>
          <h1 className="page-title" style={{ fontSize: '2.5rem', marginBottom: 10 }}>Finalize your setup</h1>
          <p className="page-subtitle">
            Provide your Upwork profile and instructions so our AI knows exactly how to represent you.
          </p>
        </div>

        {error && <div className="banner banner-error">{error}</div>}
        {success && <div className="banner banner-success">{success}</div>}

        <div className="card-elevated" style={{ padding: 30, display: 'flex', flexDirection: 'column', gap: 24 }}>

          {/* Upwork URL Section */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--on-surface-muted)' }}>Upwork Profile URL</label>
            <div style={{ display: 'flex', gap: 10 }}>
              <input
                className="input"
                type="text"
                value={profileUrl}
                onChange={(e) => setProfileUrl(e.target.value)}
                placeholder="https://upwork.com/freelancers/~..."
                style={{ flex: 1, height: 44 }}
              />
              <button
                type="button"
                disabled={extracting || !profileUrl.trim()}
                onClick={handleExtract}
                className="btn btn-ghost btn-pill btn-sm"
                style={{ height: 44, padding: '0 16px', background: 'rgba(74,222,128,0.05)', border: '1px solid rgba(74,222,128,0.2)', color: 'var(--primary)' }}
              >
                {extracting ? 'Extracting…' : 'Extract from URL'}
              </button>
            </div>
            <p style={{ fontSize: '0.7rem', color: 'var(--on-surface-muted)', fontWeight: 500 }}>
              Paste your profile link and we'll auto-extract your details.
            </p>
          </div>

          {/* Profile ID */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--on-surface-muted)' }}>Profile ID</label>
            <input
              className="input"
              type="text"
              value={profileId}
              onChange={(e) => setProfileId(e.target.value)}
              placeholder="upwork_profile_12345"
              style={{ height: 44 }}
            />
          </div>

          {/* Markdown Field */}
          <TextFieldButton
            label="Profile markdown"
            value={profileMarkdown}
            placeholder="No markdown yet. Paste raw text here and use AI to beautify it."
            modalTitle="Edit Profile Content"
            onChange={setProfileMarkdown}
            onBeautify={(draft, setDraft) => {
              void (async () => {
                if (draft.trim().length < 20) {
                  setError('Please enter at least 20 chars before beautifying.')
                  return
                }
                setBeautifying(true); setError(null)
                try {
                  const r = await beautifyManualProfile(draft)
                  setDraft(r.beautified_markdown)
                  setSuccess(`✨ Cleaned by AI using ${r.model_name}`)
                } catch (e) {
                  setError('Beautify failed. Check backend.')
                } finally {
                  setBeautifying(false)
                }
              })()
            }}
            beautifying={beautifying}
          />

          {/* Optional Global Instruction */}
          <TextFieldButton
            label="Global Instruction (Optional)"
            value={globalInstruction}
            placeholder="e.g. Always write in first person, keep it professional."
            modalTitle="Global Instructions"
            onChange={setGlobalInstruction}
          />

          <div style={{ height: 1, background: 'var(--border)', margin: '4px 0' }} />

          <button
            type="button"
            className="btn btn-primary btn-full btn-lg btn-pill"
            style={{ height: 52, fontSize: '1rem', fontWeight: 700 }}
            disabled={busy || extracting}
            onClick={handleComplete}
          >
            {busy ? 'Creating profile…' : 'Complete setup →'}
          </button>

          <p style={{ fontSize: '0.72rem', color: 'var(--on-surface-muted)', textAlign: 'center', lineHeight: 1.5 }}>
            <span style={{ color: 'var(--primary)', fontWeight: 600 }}>Note:</span> Templates for all documents are already saved as defaults.<br />
            You can customize them in your profile settings later.
          </p>
        </div>
      </div>

      <style>{`
        @keyframes scanline {
          0%   { transform: translateX(-100%); }
          100% { transform: translateX(280%); }
        }
      `}</style>
    </div>
  )
}


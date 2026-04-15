import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ApiRequestError,
  beautifyManualProfile,
  createProfile,
  extractUpworkProfile,
  getMe,
  getProfile,
  logout,
  refreshUpworkProfile,
  updateDisplayName,
  updateProfile,
  type UserProfile,
} from '../lib/api'
import { clearCurrentJobId } from '../lib/currentJob'
import { clearSessionHint } from '../lib/session'

function trimNull(v: string) { const t = v.trim(); return t || null }

/* ════════════════════════════════════════════
   Modal Editor — opens a fullscreen overlay
   for editing any long-text field
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

  /* close on Escape */
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
        {/* Modal header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 20px',
          borderBottom: beautifying ? 'none' : '1px solid var(--border)',
          flexShrink: 0,
          flexWrap: 'wrap',
          gap: 10,
        }}>
          <p className="section-label">{title}</p>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>

            {/* Beautify by AI button — only shown when handler provided */}
            {onBeautify && (
              <button
                type="button"
                disabled={beautifying || draft.trim().length < 20}
                onClick={() => onBeautify(draft, setDraft)}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 5,
                  height: 28, padding: '0 12px',
                  borderRadius: 999,
                  fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.04em',
                  background: beautifying ? 'rgba(74,222,128,0.06)' : 'rgba(74,222,128,0.12)',
                  border: '1px solid var(--border-accent)',
                  color: 'var(--primary)',
                  cursor: beautifying ? 'wait' : 'pointer',
                  transition: 'background 150ms, opacity 150ms',
                  opacity: draft.trim().length < 20 ? 0.45 : 1,
                  whiteSpace: 'nowrap',
                }}
              >
                {beautifying ? (
                  <>
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
                      style={{ animation: 'spin 0.8s linear infinite', flexShrink: 0 }}>
                      <path d="M21 12a9 9 0 11-6.219-8.56" />
                    </svg>
                    Beautifying…
                  </>
                ) : (
                  <>
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                      <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z"/>
                    </svg>
                    Beautify by AI
                  </>
                )}
              </button>
            )}

            <span style={{ fontSize: '0.72rem', color: 'var(--on-surface-muted)' }}>{wordCount} words</span>
            <button
              type="button"
              className="btn btn-sm btn-ghost"
              onClick={onClose}
              style={{ borderRadius: 8, padding: '0 10px' }}
            >
              Cancel
            </button>
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

        {/* Scanline progress bar — visible while beautifying */}
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

        {/* Divider when not beautifying */}
        {!beautifying && <div style={{ height: 1, background: 'var(--border)', flexShrink: 0 }} />}

        {/* Textarea */}
        <textarea
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={placeholder}
          style={{
            flex: 1,
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: 'var(--on-surface)',
            fontSize: '0.875rem',
            lineHeight: 1.7,
            padding: '20px 24px',
            resize: 'none',
            fontFamily: 'Inter, system-ui, sans-serif',
            overflowY: 'auto',
            minHeight: 320,
          }}
        />
      </div>
    </div>
  )
}

/* ════════════════════════════════════════════
   TextFieldButton — compact preview that opens modal
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
            height: 44,
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
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" style={{ flexShrink: 0, color: 'var(--on-surface-muted)' }}>
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
              display: 'flex', alignItems: 'center',
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
   ProfilePage
════════════════════════════════════════════ */
export function ProfilePage() {
  const navigate = useNavigate()

  const [profile, setProfile]  = useState<UserProfile | null>(null)
  const [loading, setLoading]  = useState(true)
  const [busy,    setBusy]     = useState(false)
  const [extracting,  setExtracting]  = useState(false)
  const [beautifying, setBeautifying] = useState(false)
  const [error,   setError]    = useState<string | null>(null)
  const [success, setSuccess]  = useState<string | null>(null)

  const [displayName,       setDisplayName]       = useState('')
  const [profileUrl,        setProfileUrl]        = useState('')
  const [profileId,         setProfileId]         = useState('')
  const [profileMarkdown,   setProfileMarkdown]   = useState('')
  const [proposalTemplate,  setProposalTemplate]  = useState('')
  const [docTemplate,       setDocTemplate]       = useState('')
  const [loomTemplate,      setLoomTemplate]      = useState('')
  const [workflowNotes,     setWorkflowNotes]     = useState('')
  const [globalInstruction, setGlobalInstruction] = useState('')

  useEffect(() => {
    void (async () => {
      try {
        const [r, me] = await Promise.all([getProfile(), getMe()])
        setDisplayName(me.user.display_name)
        setProfile(r)
        setProfileUrl(r.upwork_profile_url ?? '')
        setProfileId(r.upwork_profile_id ?? '')
        setProfileMarkdown(r.upwork_profile_markdown ?? '')
        setProposalTemplate(r.proposal_template ?? '')
        setDocTemplate(r.doc_template ?? '')
        setLoomTemplate(r.loom_template ?? '')
        setWorkflowNotes(r.workflow_template_notes ?? '')
        setGlobalInstruction(r.custom_global_instruction ?? '')
      } catch (e) {
        if (e instanceof ApiRequestError && e.status === 404) setProfile(null)
        else setError(e instanceof ApiRequestError ? e.message : 'Unable to load profile.')
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  /* ── Save ── */
  const handleSave = async () => {
    setBusy(true); setError(null); setSuccess(null)
    try {
      const payload = {
        upwork_profile_url:        trimNull(profileUrl),
        upwork_profile_id:         trimNull(profileId),
        upwork_profile_markdown:   trimNull(profileMarkdown),
        proposal_template:         trimNull(proposalTemplate),
        doc_template:              trimNull(docTemplate),
        loom_template:             trimNull(loomTemplate),
        workflow_template_notes:   trimNull(workflowNotes),
        custom_global_instruction: trimNull(globalInstruction),
        custom_prompt_blocks: [],
      }
      const trimmedName = displayName.trim()
      if (trimmedName) await updateDisplayName(trimmedName)
      const r = profile ? await updateProfile(payload) : await createProfile(payload)
      setProfile(r)
      setSuccess(profile ? 'Profile updated.' : 'Profile created.')
    } catch (e) {
      setError(e instanceof ApiRequestError ? e.message : 'Unexpected error.')
    } finally {
      setBusy(false)
    }
  }

  /* ── Extract from URL — calls real backend endpoint ── */
  const handleExtract = async () => {
    const url = profileUrl.trim()
    if (!url) return
    setExtracting(true); setError(null); setSuccess(null)
    try {
      /*
       * POST  → create profile if none exists, then extract
       * PATCH → re-extract into the existing profile (or use stored URL)
       */
      const r = profile
        ? await refreshUpworkProfile(url)
        : await extractUpworkProfile(url)

      /* Sync every returned field back into state */
      const p = r.profile
      setProfile(p)
      setProfileUrl(p.upwork_profile_url ?? url)
      setProfileId(p.upwork_profile_id ?? '')
      setProfileMarkdown(p.upwork_profile_markdown ?? '')
      setProposalTemplate(p.proposal_template ?? '')
      setDocTemplate(p.doc_template ?? '')
      setLoomTemplate(p.loom_template ?? '')
      setWorkflowNotes(p.workflow_template_notes ?? '')
      setGlobalInstruction(p.custom_global_instruction ?? '')
      setSuccess(r.message || 'Upwork profile extracted and saved.')
    } catch (e) {
      setError(e instanceof ApiRequestError ? e.message : 'Could not extract from URL. Ensure the backend Firecrawl key is configured.')
    } finally {
      setExtracting(false)
    }
  }

  const handleLogout = async () => {
    try { await logout() } catch { /* ok */ }
    clearCurrentJobId()
    clearSessionHint()
    navigate('/auth', { replace: true })
  }

  /* ─────────────────────────── */

  return (
    <section style={{ maxWidth: 1200, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* ── Top action bar ── */}
      <div style={{
        display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 14,
      }}>
        <div>
          <p className="page-eyebrow">Profile</p>
          <h1 className="page-title">Reusable context for every thread</h1>
          <p className="page-subtitle" style={{ maxWidth: 480 }}>
            Your identity, templates, and prompt blocks — defined once, used on every job.
          </p>
        </div>

        {/* Actions top-right */}
        {!loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0, paddingTop: 4 }}>
            <button
              type="button"
              onClick={handleLogout}
              className="btn btn-sm btn-pill"
              style={{
                background: 'rgba(248,113,113,0.08)',
                border: '1px solid rgba(248,113,113,0.2)',
                color: 'var(--danger)',
              }}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              Log out
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void handleSave()}
              className="btn btn-primary btn-pill btn-sm"
              style={{ minWidth: 130, height: 36 }}
            >
              {busy ? 'Saving…' : profile ? 'Update profile' : 'Create profile'}
            </button>
          </div>
        )}
      </div>

      {error   && <div className="banner banner-error">{error}</div>}
      {success && <div className="banner banner-success">{success}</div>}

      {loading ? (
        <div className="banner banner-info">Loading profile…</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* ── Identity card ── */}
          <div className="card-elevated" style={{ padding: 22 }}>
            <div className="section-label" style={{ marginBottom: 12 }}>Upwork Identity</div>

            {/* Profile URL + Extract */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 12 }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--on-surface-muted)' }}>Profile URL</label>
              <div style={{ display: 'flex', gap: 8 }}>
                <input
                  className="input"
                  type="text"
                  value={profileUrl}
                  onChange={(e) => setProfileUrl(e.target.value)}
                  placeholder="https://upwork.com/freelancers/~..."
                  style={{ flex: 1 }}
                />
                <button
                  type="button"
                  disabled={extracting || !profileUrl.trim()}
                  onClick={() => void handleExtract()}
                  className="btn btn-ghost btn-pill"
                  style={{ flexShrink: 0, whiteSpace: 'nowrap' }}
                >
                  {extracting ? (
                    <>
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" style={{ animation: 'spin 1s linear infinite' }}>
                        <path d="M21 12a9 9 0 11-6.219-8.56" />
                      </svg>
                      Extracting…
                    </>
                  ) : (
                    <>
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                        <polyline points="7 10 12 15 17 10" />
                        <line x1="12" y1="15" x2="12" y2="3" />
                      </svg>
                      Extract from URL
                    </>
                  )}
                </button>
              </div>
              <p style={{ fontSize: '0.72rem', color: 'var(--on-surface-muted)' }}>
                Paste your Upwork profile URL and click "Extract from URL" to auto-fill your profile markdown.
              </p>
            </div>

            {/* Display Name */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 12 }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--on-surface-muted)' }}>Name</label>
              <input
                className="input"
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Your display name"
              />
            </div>

            {/* Profile ID */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 12 }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--on-surface-muted)' }}>Profile ID</label>
              <input
                className="input"
                type="text"
                value={profileId}
                onChange={(e) => setProfileId(e.target.value)}
                placeholder="upwork_profile_12345"
              />
            </div>

            {/* Profile Markdown */}
            <TextFieldButton
              label="Profile markdown"
              value={profileMarkdown}
              placeholder="Paste raw text, bullet points, or anything about yourself — then click Beautify by AI inside the popup to clean it up."
              modalTitle="Profile Markdown"
              onChange={setProfileMarkdown}
              onBeautify={(draft, setDraft) => {
                void (async () => {
                  if (draft.trim().length < 20) {
                    setError('Please enter at least 20 characters of profile text before beautifying.')
                    return
                  }
                  setBeautifying(true); setError(null); setSuccess(null)
                  try {
                    const r = await beautifyManualProfile(draft)
                    setDraft(r.beautified_markdown)
                    setSuccess(`✨ Beautified by AI — ${r.input_tokens} in / ${r.output_tokens} out tokens (${r.model_name})`)
                  } catch (e) {
                    setError(e instanceof ApiRequestError ? e.message : 'Beautify failed. Check backend AI key.')
                  } finally {
                    setBeautifying(false)
                  }
                })()
              }}
              beautifying={beautifying}
            />
          </div>

          {/* ── Global instruction ── */}
          <div className="card-elevated" style={{ padding: 22 }}>
            <div className="section-label" style={{ marginBottom: 12 }}>Global Instruction</div>
            <TextFieldButton
              label="Applied to every generation run"
              value={globalInstruction}
              placeholder="e.g. Always write in first person. Keep proposals under 300 words. Avoid jargon."
              modalTitle="Global Instruction"
              onChange={setGlobalInstruction}
            />
          </div>

          {/* ── Output templates ── */}
          <div className="card-elevated" style={{ padding: 22 }}>
            <div className="section-label" style={{ marginBottom: 14 }}>Output Templates</div>
            <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))' }}>
              <TextFieldButton label="Proposal" value={proposalTemplate} placeholder="Default proposal structure…" modalTitle="Proposal Template" onChange={setProposalTemplate} />
              <TextFieldButton label="Document" value={docTemplate} placeholder="Default document structure…" modalTitle="Document Template" onChange={setDocTemplate} />
              <TextFieldButton label="Loom script" value={loomTemplate} placeholder="Default Loom video script…" modalTitle="Loom Script Template" onChange={setLoomTemplate} />
              <TextFieldButton label="Workflow notes" value={workflowNotes} placeholder="Default workflow notes…" modalTitle="Workflow Notes Template" onChange={setWorkflowNotes} />
            </div>
          </div>

          {/* ── Bottom save ── */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, paddingBottom: 24 }}>
            <button
              type="button"
              onClick={handleLogout}
              className="btn btn-sm btn-pill"
              style={{ background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.2)', color: 'var(--danger)' }}
            >
              Log out
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void handleSave()}
              className="btn btn-primary btn-pill"
              style={{ minWidth: 150, height: 42 }}
            >
              {busy ? 'Saving…' : profile ? 'Update profile' : 'Create profile'}
            </button>
          </div>
        </div>
      )}

      {/* Keyframes */}
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        @keyframes scanline {
          0%   { transform: translateX(-100%); }
          100% { transform: translateX(280%); }
        }
      `}</style>
    </section>
  )
}

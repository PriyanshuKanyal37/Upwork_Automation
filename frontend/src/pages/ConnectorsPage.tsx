import { useEffect, useRef, useState } from 'react'
import {
  ApiRequestError,
  createConnector,
  deleteConnector,
  getConnectorStatus,
  listConnectors,
  startGoogleOAuth,
  updateConnector,
  type ConnectorRecord,
  type ConnectorStatus,
} from '../lib/api'


/* ─── Status badge ─── */
function StatusBadge({ status }: { status: string }) {
  const isConnected = status === 'connected'
  const isError     = status === 'error' || status === 'expired'
  const isPending   = status === 'pending_oauth'

  const color  = isConnected ? 'var(--primary)' : isError ? 'var(--danger)' : isPending ? 'var(--warning)' : 'var(--on-surface-muted)'
  const bg     = isConnected ? 'rgba(91,168,160,0.12)' : isError ? 'rgba(248,113,113,0.1)' : isPending ? 'rgba(251,191,36,0.1)' : 'rgba(255,255,255,0.05)'
  const border = isConnected ? 'rgba(91,168,160,0.28)' : isError ? 'rgba(248,113,113,0.25)' : isPending ? 'rgba(251,191,36,0.25)' : 'rgba(255,255,255,0.08)'
  const dot    = isConnected ? 'var(--primary)' : isError ? 'var(--danger)' : isPending ? 'var(--warning)' : 'var(--on-surface-subtle)'
  const text   = isConnected ? 'Connected' : isError ? status.replace(/_/g, ' ') : isPending ? 'Pending' : status.replace(/_/g, ' ')

  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      height: 24, padding: '0 10px', borderRadius: 999,
      fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.06em',
      textTransform: 'capitalize',
      background: bg, color, border: `1px solid ${border}`,
    }}>
      <span style={{
        width: 6, height: 6, borderRadius: '50%', background: dot, flexShrink: 0,
        boxShadow: isConnected ? '0 0 5px var(--primary)' : undefined,
        animation: isConnected ? 'connPulse 2.2s ease-in-out infinite' : undefined,
      }} />
      {text}
    </span>
  )
}

/* ════════════════════════════════════════
   Google Docs Card — OAuth-based
════════════════════════════════════════ */
function GoogleDocsCard({
  record,
  liveStatus,
  busy,
  onOAuthConnect,
  onLive,
  onDisconnect,
  onDelete,
}: {
  record?: ConnectorRecord
  liveStatus?: ConnectorStatus
  busy: boolean
  onOAuthConnect: () => void
  onLive: () => void
  onDisconnect: () => void
  onDelete: () => void
}) {
  const isConnected = record?.status === 'connected'
  const isPending   = record?.status === 'pending_oauth'

  return (
    <article style={{
      background: 'var(--surface-container)',
      border: `1px solid ${isConnected ? 'rgba(91,168,160,0.22)' : 'var(--border)'}`,
      borderRadius: 16,
      overflow: 'hidden',
      transition: 'border-color 200ms',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '20px 22px', gap: 16, flexWrap: 'wrap',
        background: isConnected
          ? 'linear-gradient(120deg, rgba(91,168,160,0.06) 0%, transparent 70%)'
          : 'transparent',
      }}>
        {/* Left */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, minWidth: 0 }}>
          <div style={{
            width: 46, height: 46, borderRadius: 12, flexShrink: 0,
            background: isConnected ? 'rgba(91,168,160,0.12)' : 'rgba(255,255,255,0.04)',
            border: `1px solid ${isConnected ? 'rgba(91,168,160,0.22)' : 'rgba(255,255,255,0.07)'}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.4rem',
          }}>
            📄
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
              <p style={{ fontSize: '0.9375rem', fontWeight: 700, color: 'var(--on-surface)' }}>
                Google Docs
              </p>
              {record
                ? <StatusBadge status={record.status} />
                : <StatusBadge status="disconnected" />
              }
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--on-surface-muted)', lineHeight: 1.5 }}>
              Publish proposals and documents directly as Google Docs drafts in your Drive.
            </p>
            {isPending && (
              <p style={{ marginTop: 6, fontSize: '0.78rem', color: 'var(--warning)' }}>
                ⚠ OAuth pending — reconnect to complete authorisation.
              </p>
            )}
            {(record?.status === 'expired' || record?.status === 'error') && (
              <p style={{ marginTop: 6, fontSize: '0.78rem', color: 'var(--danger)' }}>
                ⚠ Session expired — reconnect with Google to restore access.
              </p>
            )}
          </div>
        </div>

        {/* Right — actions */}
        <div style={{ display: 'flex', gap: 8, flexShrink: 0, flexWrap: 'wrap', alignItems: 'center' }}>
          {isConnected && (
            <button type="button" disabled={busy} onClick={onLive} className="btn btn-ghost btn-sm btn-pill">
              Live check
            </button>
          )}
          {isConnected ? (
            <button
              type="button" disabled={busy} onClick={onDisconnect}
              className="btn btn-ghost btn-sm btn-pill"
            >
              Disconnect
            </button>
          ) : (
            /* THE Connect with Google button */
            <button
              type="button"
              disabled={busy}
              onClick={onOAuthConnect}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 8,
                height: 36, padding: '0 16px', borderRadius: 999,
                background: '#fff', color: '#3c4043',
                border: '1px solid rgba(255,255,255,0.15)',
                fontWeight: 600, fontSize: '0.875rem', cursor: 'pointer',
                boxShadow: '0 1px 8px rgba(0,0,0,0.3)',
                transition: 'box-shadow 150ms, opacity 150ms',
                opacity: busy ? 0.5 : 1,
              }}
            >

              {busy ? (
                <span style={{
                  width: 16, height: 16, borderRadius: '50%', flexShrink: 0,
                  border: '2px solid rgba(60,64,67,0.3)', borderTopColor: '#4285F4',
                  display: 'inline-block', animation: 'spin 0.8s linear infinite',
                }} />
              ) : (
                <svg width="18" height="18" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
                  <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
                  <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
                  <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
                  <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.36-8.16 2.36-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
                </svg>
              )}
              {busy ? 'Connecting…' : 'Connect with Google'}
            </button>
          )}
          {record && (
            <button
              type="button" disabled={busy} onClick={onDelete}
              className="btn btn-sm btn-pill"
              style={{ background: 'rgba(248,113,113,0.07)', color: 'var(--danger)', border: '1px solid rgba(248,113,113,0.18)' }}
            >
              Remove
            </button>
          )}
        </div>
      </div>

      {/* Live check result */}
      {liveStatus && (
        <div style={{
          margin: '0 20px 16px', padding: '10px 14px', borderRadius: 10,
          background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <StatusBadge status={liveStatus.status} />
          <p style={{ fontSize: '0.8125rem', color: 'var(--on-surface-muted)' }}>{liveStatus.message}</p>
        </div>
      )}
    </article>
  )
}

/* ════════════════════════════════════════
   API Key Card (Firecrawl, n8n)
════════════════════════════════════════ */
interface ApiKeyDef {
  name: 'firecrawl' | 'n8n'
  label: string
  icon: string
  description: string
  placeholder: string
  hint: string
}

const API_KEY_DEFS: ApiKeyDef[] = [
  {
    name: 'firecrawl',
    label: 'Firecrawl',
    icon: '🔥',
    description: "Extracts job markdown from Upwork listings via Firecrawl's scraping API.",
    placeholder: 'fc-xxxxxxxxxxxxxxxxxxxxxxxx',
    hint: 'Paste your Firecrawl API key from app.firecrawl.dev',
  },
  {
    name: 'n8n',
    label: 'n8n',
    icon: '⚡',
    description: 'Triggers n8n workflows for publishing, notifications, and downstream automation.',
    placeholder: 'https://your-instance.n8n.cloud/webhook/xxx',
    hint: 'Paste your n8n webhook URL or API key',
  },
]

function ApiKeyCard({
  def,
  record,
  liveStatus,
  busy,
  onSave,
  onLive,
  onDisconnect,
  onDelete,
}: {
  def: ApiKeyDef
  record?: ConnectorRecord
  liveStatus?: ConnectorStatus
  busy: boolean
  onSave: (key: string) => void
  onLive: () => void
  onDisconnect: () => void
  onDelete: () => void
}) {
  const isConnected = record?.status === 'connected'
  const getCleanKey = (raw: string) => {
    if (def.name === 'firecrawl' && raw.startsWith('firecrawl://')) {
      return raw.replace('firecrawl://', '')
    }
    // Also handle generic prefixes just in case we add more simple API keys
    if (raw.includes('://')) {
      const parts = raw.split('://')
      if (parts[0] === def.name) return parts.slice(1).join('://')
    }
    return raw
  }

  const [apiKey, setApiKey] = useState(() => getCleanKey(record?.credential_ref ?? ''))
  const [editing, setEditing] = useState(!record)

  useEffect(() => {
    setApiKey(getCleanKey(record?.credential_ref ?? ''))
    if (!record) setEditing(true)
  }, [record?.credential_ref])

  const maskedKey = apiKey.length > 8
    ? `${apiKey.slice(0, 6)}${'•'.repeat(Math.min(apiKey.length - 8, 20))}${apiKey.slice(-4)}`
    : '••••••••'

  return (
    <article style={{
      background: 'var(--surface-container)',
      border: `1px solid ${isConnected ? 'rgba(91,168,160,0.22)' : 'var(--border)'}`,
      borderRadius: 16,
      overflow: 'hidden',
      transition: 'border-color 200ms',
    }}>
      {/* Header row */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '20px 22px', gap: 16, flexWrap: 'wrap',
        background: isConnected
          ? 'linear-gradient(120deg, rgba(91,168,160,0.06) 0%, transparent 70%)'
          : 'transparent',
        borderBottom: editing ? '1px solid var(--border)' : 'none',
      }}>
        {/* Left */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, minWidth: 0 }}>
          <div style={{
            width: 46, height: 46, borderRadius: 12, flexShrink: 0,
            background: isConnected ? 'rgba(91,168,160,0.12)' : 'rgba(255,255,255,0.04)',
            border: `1px solid ${isConnected ? 'rgba(91,168,160,0.22)' : 'rgba(255,255,255,0.07)'}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.4rem',
          }}>
            {def.icon}
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
              <p style={{ fontSize: '0.9375rem', fontWeight: 700, color: 'var(--on-surface)' }}>
                {def.label}
              </p>
              {record
                ? <StatusBadge status={record.status} />
                : <StatusBadge status="disconnected" />
              }
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--on-surface-muted)', lineHeight: 1.5 }}>
              {def.description}
            </p>
            {record && !editing && (
              <p style={{
                marginTop: 5, fontSize: '0.78rem', color: 'var(--on-surface-subtle)',
                fontFamily: 'monospace', letterSpacing: '0.04em',
              }}>
                {maskedKey}
              </p>
            )}
          </div>
        </div>

        {/* Right — actions */}
        <div style={{ display: 'flex', gap: 8, flexShrink: 0, flexWrap: 'wrap', alignItems: 'center' }}>
          {isConnected && (
            <button type="button" disabled={busy} onClick={onLive} className="btn btn-ghost btn-sm btn-pill">
              Live check
            </button>
          )}
          {isConnected && (
            <button type="button" disabled={busy} onClick={onDisconnect} className="btn btn-ghost btn-sm btn-pill">
              Disconnect
            </button>
          )}
          {record && (
            <button
              type="button" onClick={() => setEditing(v => !v)}
              className="btn btn-ghost btn-sm btn-pill"
            >
              {editing ? 'Cancel' : 'Edit key'}
            </button>
          )}
          {record && (
            <button
              type="button" disabled={busy} onClick={onDelete}
              className="btn btn-sm btn-pill"
              style={{ background: 'rgba(248,113,113,0.07)', color: 'var(--danger)', border: '1px solid rgba(248,113,113,0.18)' }}
            >
              Remove
            </button>
          )}
        </div>
      </div>

      {/* API key input — shown when configuring or editing */}
      {editing && (
        <div style={{ padding: '18px 22px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <label style={{
              fontSize: '0.75rem', fontWeight: 600, color: 'var(--on-surface-muted)',
              display: 'block', marginBottom: 6,
            }}>
              API Key
            </label>
            <input
              className="input"
              type="text"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              placeholder={def.placeholder}
              autoFocus
              autoComplete="off"
              data-form-type="other"
              spellCheck={false}
            />
            <p style={{ marginTop: 5, fontSize: '0.75rem', color: 'var(--on-surface-subtle)' }}>
              {def.hint}
            </p>
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button
              type="button"
              disabled={busy || apiKey.trim().length < 4}
              onClick={() => { onSave(apiKey.trim()); setEditing(false) }}
              className="btn btn-primary btn-pill"
            >
              {record ? 'Update key' : 'Save & connect'}
            </button>
          </div>
        </div>
      )}

      {/* Live check result */}
      {liveStatus && (
        <div style={{
          margin: '0 20px 16px', padding: '10px 14px', borderRadius: 10,
          background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <StatusBadge status={liveStatus.status} />
          <p style={{ fontSize: '0.8125rem', color: 'var(--on-surface-muted)' }}>{liveStatus.message}</p>
        </div>
      )}
    </article>
  )
}

/* ════════════════════════════════════════
   Page
════════════════════════════════════════ */
export function ConnectorsPage() {
  const [connectors,      setConnectors]      = useState<ConnectorRecord[]>([])
  const [statusMap,       setStatusMap]       = useState<Record<string, ConnectorStatus>>({})
  const [busy,            setBusy]            = useState<string | null>(null)
  const [error,           setError]           = useState<string | null>(null)
  const [success,         setSuccess]         = useState<string | null>(null)
  const [googleConnecting, setGoogleConnecting] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = async () => {
    const r = await listConnectors()
    setConnectors(r.connectors)
  }

  useEffect(() => {
    void (async () => {
      try { await load() }
      catch (e) { setError(e instanceof ApiRequestError ? e.message : 'Unable to load connectors.') }
    })()
    // cleanup polling on unmount
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  const run = async (key: string, fn: () => Promise<void>) => {
    setBusy(key); setError(null); setSuccess(null)
    try { await fn() }
    catch (e) { setError(e instanceof ApiRequestError ? e.message : 'Unexpected error.') }
    finally { setBusy(null) }
  }

  /* ── Google OAuth popup + polling ── */
  const handleGoogleOAuth = async () => {
    setError(null); setSuccess(null)
    setGoogleConnecting(true)
    try {
      const { authorization_url } = await startGoogleOAuth()

      // Open Google's account chooser in a popup
      const popup = window.open(
        authorization_url,
        'google_oauth',
        'width=520,height=640,scrollbars=yes,resizable=yes,toolbar=no,menubar=no'
      )

      // Poll every 2s — detect when google_docs connector becomes connected
      let elapsed = 0
      const TIMEOUT_MS = 5 * 60 * 1000 // 5 min max
      pollRef.current = setInterval(async () => {
        elapsed += 2000
        try {
          const r = await listConnectors()
          const gDoc = r.connectors.find(c => c.connector_name === 'google_docs')
          if (gDoc?.status === 'connected') {
            if (pollRef.current) clearInterval(pollRef.current)
            popup?.close()
            setConnectors(r.connectors)
            setGoogleConnecting(false)
            setSuccess('Google Docs connected successfully!')
            return
          }
        } catch { /* ignore poll errors */ }

        // Stop if popup was manually closed
        if (popup?.closed) {
          if (pollRef.current) clearInterval(pollRef.current)
          setGoogleConnecting(false)
          return
        }

        // Timeout
        if (elapsed >= TIMEOUT_MS) {
          if (pollRef.current) clearInterval(pollRef.current)
          popup?.close()
          setGoogleConnecting(false)
          setError('Google authorisation timed out. Please try again.')
        }
      }, 2000)
    } catch (e) {
      setGoogleConnecting(false)
      setError(e instanceof ApiRequestError ? e.message : 'Could not start Google OAuth.')
    }
  }

  const connectedCount = connectors.filter(c => c.status === 'connected').length
  const totalConnectors = 1 + API_KEY_DEFS.length
  const googleRecord   = connectors.find(c => c.connector_name === 'google_docs')

  return (
    <>
      <style>{`
        @keyframes connPulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.35; }
        }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>

      <section style={{ maxWidth: 840, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 28 }}>

        {/* Header */}
        <header style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
          <div>
            <p className="page-eyebrow">Connectors</p>
            <h1 className="page-title">Publish destinations</h1>
            <p className="page-subtitle" style={{ maxWidth: 460 }}>
              Connect third-party tools to unlock publishing, extraction, and automation.
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{
              fontSize: '0.8rem', color: 'var(--on-surface-muted)',
              background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)',
              borderRadius: 999, padding: '4px 12px',
            }}>
              {connectedCount}/{totalConnectors} connected
            </span>
            <button
              type="button" disabled={busy !== null}
              className="btn btn-ghost btn-sm btn-pill"
              onClick={() => run('refresh', async () => { await load(); setSuccess('Refreshed.') })}
            >
              Refresh
            </button>
          </div>
        </header>

        {error   && <div className="banner banner-error">{error}</div>}
        {success && <div className="banner banner-success">{success}</div>}

        {/* Cards */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

          {/* Google Docs — OAuth flow */}
          <GoogleDocsCard
            record={googleRecord}
            liveStatus={statusMap['google_docs']}
            busy={busy !== null || googleConnecting}
            onOAuthConnect={() => void handleGoogleOAuth()}
            onLive={() => run('live-google_docs', async () => {
              const r = await getConnectorStatus('google_docs', { live: true })
              setStatusMap(prev => ({ ...prev, google_docs: r.connector_status }))
              setSuccess('Live check done for Google Docs.')
            })}
            onDisconnect={() => run('toggle-google_docs', async () => {
              await updateConnector('google_docs', { status: 'disconnected' })
              await load(); setSuccess('Google Docs disconnected.')
            })}
            onDelete={() => run('delete-google_docs', async () => {
              await deleteConnector('google_docs')
              setStatusMap(prev => { const n = { ...prev }; delete n.google_docs; return n })
              await load(); setSuccess('Google Docs removed.')
            })}
          />

          {/* Firecrawl + n8n — API key flow */}
          {API_KEY_DEFS.map(def => {
            const record = connectors.find(c => c.connector_name === def.name)
            return (
              <ApiKeyCard
                key={def.name}
                def={def}
                record={record}
                liveStatus={statusMap[def.name]}
                busy={busy !== null}
                onSave={key => run(`save-${def.name}`, async () => {
                  if (record) {
                    await updateConnector(def.name, { credential_ref: key, status: 'connected' })
                  } else {
                    await createConnector({ connector_name: def.name, credential_ref: key, status: 'connected' })
                  }
                  await load()
                  setSuccess(`${def.label} connected.`)
                })}
                onLive={() => run(`live-${def.name}`, async () => {
                  const r = await getConnectorStatus(def.name, { live: true })
                  setStatusMap(prev => ({ ...prev, [def.name]: r.connector_status }))
                  setSuccess(`Live check done for ${def.label}.`)
                })}
                onDisconnect={() => run(`toggle-${def.name}`, async () => {
                  await updateConnector(def.name, { status: 'disconnected' })
                  await load(); setSuccess(`${def.label} disconnected.`)
                })}
                onDelete={() => run(`delete-${def.name}`, async () => {
                  await deleteConnector(def.name)
                  setStatusMap(prev => { const n = { ...prev }; delete n[def.name]; return n })
                  await load(); setSuccess(`${def.label} removed.`)
                })}
              />
            )
          })}
        </div>

        {/* Note about Google OAuth */}
        <p style={{ fontSize: '0.78rem', color: 'var(--on-surface-subtle)', textAlign: 'center', lineHeight: 1.7 }}>
          Google Docs uses OAuth 2.0 — clicking "Connect with Google" opens Google's account chooser popup.<br />
          Firecrawl and n8n use API keys stored as encrypted credential references.
        </p>
      </section>
    </>
  )
}


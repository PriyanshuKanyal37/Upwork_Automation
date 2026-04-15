import { useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { WorkflowVisualizer } from '../components/WorkflowVisualizer'
import type { KeyboardEvent, ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  ApiRequestError,
  approveJob,
  createJobIntake,
  explainJob,
  extractJob,
  getJobDetail,
  listConnectors,
  listGenerationRuns,
  publishJob,
  regenerateOutput,
  generateDocFlowchart,
  getJobOutputs,
  saveManualMarkdown,
  sendDuplicateDecision,
  updateJobOutputs,
  updateJobStatusOutcome,
  updateJobSubmission,
  type ConnectorRecord,
  type GenerationRun,
  type JobOutcome,
  type JobOutput,
  type JobRecord,
  type PublishResult,
} from '../lib/api'
import { clearCurrentJobId, getCurrentJobId, setCurrentJobId } from '../lib/currentJob'
import { notifyJobsHistoryRefresh } from '../lib/events'
import { deriveJobTitle } from '../lib/jobTitles'

/* ══════════════════════════════════════════
   Helpers
══════════════════════════════════════════ */
function preview(value: string, max = 500) {
  return value.length > max ? `${value.slice(0, max)}\n\n…` : value
}
function readableLabel(v: string | null | undefined) {
  return v ? v.replace(/_/g, ' ') : 'Not set'
}
function wordCount(v: string) {
  return v.trim().split(/\s+/).filter(Boolean).length
}
const platformLabel: Record<string, string> = {
  n8n: 'n8n',
  make: 'Make.com',
  ghl: 'GoHighLevel',
}
function getPlatformName(platform: string | null | undefined): string {
  return platformLabel[String(platform ?? '').toLowerCase()] ?? 'Automation'
}

function extractGoogleDriveFileId(url: string | null | undefined): string | null {
  if (!url) return null
  try {
    const parsed = new URL(url)
    const queryId = parsed.searchParams.get('id')
    if (queryId) return queryId
    const pathMatch = parsed.pathname.match(/\/d\/([a-zA-Z0-9_-]+)/)
    if (pathMatch?.[1]) return pathMatch[1]
  } catch {
    return null
  }
  return null
}

function driveThumbnailUrl(url: string | null | undefined): string | null {
  const fileId = extractGoogleDriveFileId(url)
  return fileId ? `https://drive.google.com/thumbnail?id=${fileId}&sz=w2000` : null
}

function driveDownloadUrl(url: string | null | undefined): string | null {
  const fileId = extractGoogleDriveFileId(url)
  return fileId ? `https://drive.google.com/uc?export=download&id=${fileId}` : null
}

function buildDiagramImageCandidates(diagram: JobOutput['doc_flowchart'] | null | undefined): string[] {
  if (!diagram) return []
  const url = diagram.image_url
  const fileId = extractGoogleDriveFileId(url)
  const candidates = [
    diagram.inline_svg_data_url || null,
    url,
    driveThumbnailUrl(url),
    fileId ? `https://drive.google.com/uc?export=view&id=${fileId}` : null,
    driveDownloadUrl(url),
  ]
  return Array.from(new Set(candidates.filter((value): value is string => Boolean(value))))
}

/* ══════════════════════════════════════════
   Chat bubble
══════════════════════════════════════════ */
function Bubble({
  role,
  label,
  accent,
  children,
  animateIn,
}: {
  role: 'user' | 'ai' | 'system'
  label?: string
  accent?: boolean
  children: ReactNode
  animateIn?: boolean
}) {
  const isUser = role === 'user'
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: isUser ? 'row-reverse' : 'row',
        gap: 10,
        alignItems: 'flex-start',
        animation: animateIn ? 'bubbleIn 280ms cubic-bezier(0.34,1.56,0.64,1) forwards' : undefined,
        opacity: animateIn ? 0 : 1,
      }}
    >
      {/* Avatar dot */}
      <div style={{
        width: 28, height: 28, borderRadius: '50%', flexShrink: 0, marginTop: 2,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: isUser
          ? 'rgba(255,255,255,0.06)'
          : accent
            ? 'linear-gradient(135deg, rgba(74,222,128,0.25), rgba(74,222,128,0.08))'
            : 'rgba(74,222,128,0.08)',
        border: isUser ? '1px solid rgba(255,255,255,0.09)' : '1px solid rgba(74,222,128,0.2)',
        fontSize: '0.6rem', fontWeight: 700,
        color: isUser ? 'var(--on-surface-muted)' : 'var(--primary)',
      }}>
        {isUser ? 'U' : role === 'system' ? '⚡' : '✦'}
      </div>

      {/* Bubble body */}
      <div style={{
        maxWidth: 'min(680px, 85%)',
        padding: '14px 18px',
        borderRadius: isUser ? '16px 4px 16px 16px' : '4px 16px 16px 16px',
        background: isUser
          ? 'rgba(255,255,255,0.04)'
          : accent
            ? 'linear-gradient(160deg, rgba(74,222,128,0.1), rgba(74,222,128,0.03))'
            : 'rgba(255,255,255,0.025)',
        border: `1px solid ${isUser ? 'rgba(255,255,255,0.07)' : accent ? 'rgba(74,222,128,0.22)' : 'rgba(255,255,255,0.06)'}`,
        backdropFilter: 'blur(4px)',
      }}>
        {label && (
          <p style={{
            fontSize: '0.62rem', fontWeight: 700, letterSpacing: '0.13em',
            textTransform: 'uppercase', color: accent ? 'var(--primary)' : 'var(--on-surface-subtle)',
            marginBottom: 10,
          }}>
            {label}
          </p>
        )}
        {children}
      </div>
    </div>
  )
}

/* ══════════════════════════════════════════
   Output Preview Modal
══════════════════════════════════════════ */
function OutputArtifactView({
  type,
  label,
  content,
  field,
  busyAction,
  onSave,
  onRegenerate
}: {
  type: 'proposal' | 'doc' | 'loom_script' | 'workflow'
  label: string
  content: string
  field: 'proposal_text' | 'google_doc_markdown' | 'loom_script' | null
  busyAction: string | null
  onSave: (field: 'proposal_text' | 'google_doc_markdown' | 'loom_script', v: string) => Promise<void>
  onRegenerate: (type: 'proposal' | 'doc' | 'loom_script' | 'workflow', instruction: string) => Promise<void>
}) {
  const [editMode, setEditMode] = useState(false)
  const [draft, setDraft] = useState('')
  const [instruction, setInstruction] = useState('')
  const [copied, setCopied] = useState(false)
  const [viewMode, setViewMode] = useState<'json' | 'visual'>(type === 'workflow' ? 'visual' : 'json')
  // Ref to the rendered doc-preview div so the Copy button can read its
  // innerHTML and push rich HTML to the clipboard (pastes into Google Docs
  // with formatting preserved).
  const previewRef = useRef<HTMLDivElement | null>(null)
  // Types that render as styled markdown (not workflow JSON).
  const isMarkdownType = type === 'doc' || type === 'proposal' || type === 'loom_script'

  useEffect(() => { setDraft(content); setEditMode(false) }, [content])

  const handleSave = async () => {
    if (!field) return
    await onSave(field, draft)
    setEditMode(false)
  }

  const handleCopy = async () => {
    try {
      // For markdown types, write BOTH text/html (rendered preview) AND
      // text/plain (raw markdown) to the clipboard. Google Docs reads the
      // HTML flavor on paste, so headings, tables, bold, and bullets come
      // through as proper Google Docs styles.
      const html = isMarkdownType && previewRef.current ? previewRef.current.innerHTML : null
      if (html && typeof ClipboardItem !== 'undefined' && navigator.clipboard?.write) {
        const htmlBlob = new Blob([html], { type: 'text/html' })
        const textBlob = new Blob([content], { type: 'text/plain' })
        await navigator.clipboard.write([
          new ClipboardItem({
            'text/html': htmlBlob,
            'text/plain': textBlob,
          }),
        ])
      } else {
        await navigator.clipboard.writeText(content)
      }
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      // Fallback: try plain text copy so the button always does something useful
      try {
        await navigator.clipboard.writeText(content)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      } catch (fallbackErr) {
        console.error('Failed to copy text:', err, fallbackErr)
      }
    }
  }

  return (
    <div style={{
      background: 'var(--surface-container)',
      border: '1px solid var(--border)',
      borderRadius: 16,
      overflow: 'hidden',
      marginBottom: 20,
      boxShadow: '0 4px 24px rgba(0,0,0,0.2)',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 20px', borderBottom: '1px solid var(--border)', background: 'rgba(255,255,255,0.02)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <h3 style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--on-surface)' }}>{label}</h3>
          {type === 'workflow' && content && (
            <div style={{ 
              display: 'flex', background: 'rgba(0,0,0,0.3)', borderRadius: 10, padding: 3, 
              border: '1px solid var(--border)', boxShadow: 'inset 0 1px 4px rgba(0,0,0,0.2)' 
            }}>
              <button
                type="button"
                onClick={() => setViewMode('json')}
                style={{
                  padding: '5px 12px', fontSize: '0.75rem', fontWeight: 700, borderRadius: 8, cursor: 'pointer',
                  background: viewMode === 'json' ? 'var(--surface-high)' : 'transparent',
                  color: viewMode === 'json' ? 'var(--primary)' : 'var(--on-surface-muted)',
                  border: 'none', transition: 'all 200ms cubic-bezier(0.4, 0, 0.2, 1)',
                  display: 'flex', alignItems: 'center', gap: 6
                }}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
                JSON
              </button>
              <button
                type="button"
                onClick={() => setViewMode('visual')}
                style={{
                  padding: '5px 12px', fontSize: '0.75rem', fontWeight: 700, borderRadius: 8, cursor: 'pointer',
                  background: viewMode === 'visual' ? 'var(--surface-high)' : 'transparent',
                  color: viewMode === 'visual' ? 'var(--primary)' : 'var(--on-surface-muted)',
                  border: 'none', transition: 'all 200ms cubic-bezier(0.4, 0, 0.2, 1)',
                  display: 'flex', alignItems: 'center', gap: 6
                }}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
                Visualize
              </button>
            </div>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {content && (
            <button
              type="button"
              className="btn btn-sm btn-ghost btn-pill"
              onClick={handleCopy}
              style={{ color: copied ? 'var(--primary)' : 'inherit', minWidth: 64 }}
            >
              {copied ? 'Copied!' : type === 'workflow' ? 'Copy JSON' : 'Copy'}
            </button>
          )}
          {field && !editMode && (
            <button type="button" className="btn btn-sm btn-ghost btn-pill" onClick={() => { setDraft(content); setEditMode(true) }}>
              Edit
            </button>
          )}
          {editMode && (
            <>
              <button type="button" className="btn btn-sm btn-ghost btn-pill" onClick={() => setEditMode(false)}>Cancel</button>
              <button type="button" disabled={busyAction !== null} className="btn btn-sm btn-primary btn-pill" onClick={handleSave}>
                {busyAction?.startsWith('save') ? 'Saving…' : 'Save'}
              </button>
            </>
          )}
        </div>
      </div>
      
      {/* Content */}
      <div style={type === 'workflow' && viewMode === 'visual' ? { overflow: 'hidden' } : { padding: '20px 24px', maxHeight: 500, overflowY: 'auto' }}>
        {editMode && field ? (
          <textarea
            autoFocus
            value={draft}
            onChange={e => setDraft(e.target.value)}
            style={{
              width: '100%', minHeight: 400, background: 'rgba(0,0,0,0.15)',
              border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12, padding: '16px 20px',
              color: 'var(--on-surface)', fontSize: '0.875rem', lineHeight: 1.6, resize: 'vertical',
              outline: 'none', fontFamily: 'Inter, system-ui, sans-serif'
            }}
          />
        ) : type === 'workflow' ? (
          content ? (
            viewMode === 'visual' ? (
              <WorkflowVisualizer content={content} />
            ) : (
            <div style={{ 
              background: 'linear-gradient(180deg, rgba(0,0,0,0.3) 0%, rgba(0,0,0,0.1) 100%)',
              borderRadius: 12, border: '1px solid rgba(255,255,255,0.04)', padding: '16px 20px'
            }}>
              <pre style={{
                margin: 0, whiteSpace: 'pre-wrap', fontFamily: '"JetBrains Mono", "Fira Code", monospace',
                fontSize: '0.8rem', lineHeight: 1.6, color: 'var(--primary)', opacity: 0.9,
              }}>
                {content}
              </pre>
            </div>         
            )
          ) : (
            <div style={{ padding: '24px 20px', color: 'var(--on-surface-muted)', fontSize: '0.875rem' }}>No workflow available yet.</div>
          )
        ) : isMarkdownType ? (
          // Styled Google-Docs-like rendering. User can select + copy from
          // this div and the browser will put rich HTML on the clipboard.
          // The Copy button also uses previewRef.current.innerHTML for one-
          // click rich copy.
          content ? (
            <div ref={previewRef} className="doc-preview">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {content}
              </ReactMarkdown>
            </div>
          ) : (
            <div style={{ color: 'var(--on-surface-muted)', fontSize: '0.875rem' }}>No content yet.</div>
          )
        ) : (
          <pre style={{
            whiteSpace: 'pre-wrap', fontFamily: 'Inter, system-ui, sans-serif',
            fontSize: '0.875rem', lineHeight: 1.75, color: 'var(--on-surface)',
          }}>
            {content || <span style={{ color: 'var(--on-surface-muted)' }}>No content yet.</span>}
          </pre>
        )}
      </div>

      {/* Footer / Regen */}
      <div style={{
        padding: '12px 20px', borderTop: '1px solid var(--border)', background: 'rgba(255,255,255,0.01)',
        display: 'flex', gap: 12, alignItems: 'center'
      }}>
        <input 
          className="input" 
          type="text"
          value={instruction}
          onChange={e => setInstruction(e.target.value)}
          placeholder={`Instructions to regenerate ${label.toLowerCase()}...`}
          style={{ flex: 1, height: 36, fontSize: '0.8125rem', background: 'rgba(0,0,0,0.2)' }}
        />
        <button
          type="button"
          disabled={busyAction !== null}
          className="btn btn-sm btn-ghost btn-pill"
          style={{ color: 'var(--primary)', borderColor: 'var(--border-accent)', background: 'var(--primary-glow)' }}
          onClick={() => void onRegenerate(type, instruction)}
        >
          {busyAction === `regen-${type}` ? 'Regenerating…' : '✦ Regenerate'}
        </button>
      </div>
    </div>
  )
}

/* ══════════════════════════════════════════
   Spinner dots
══════════════════════════════════════════ */
function ThinkingDots() {
  return (
    <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
      {[0, 1, 2].map(i => (
        <span key={i} style={{
          width: 6, height: 6, borderRadius: '50%',
          background: 'var(--primary)',
          display: 'inline-block',
          animation: `dotPulse 1.2s ease-in-out ${i * 0.2}s infinite`,
        }} />
      ))}
    </span>
  )
}

/* ══════════════════════════════════════════
   WorkspacePage
══════════════════════════════════════════ */
export function WorkspacePage() {
  const location = useLocation()
  const navigate  = useNavigate()
  const threadRef = useRef<HTMLDivElement>(null)

  // ── Core state ──
  const [jobId,      setJobId]      = useState<string | null>(null)
  const [job,        setJob]        = useState<JobRecord | null>(null)
  const [output,     setOutput]     = useState<JobOutput | null>(null)
  const [runs,       setRuns]       = useState<GenerationRun[]>([])
  const [duplicateNames, setDuplicateNames] = useState<string[]>([])
  const [connectors, setConnectors] = useState<ConnectorRecord[]>([])
  const [loading,    setLoading]    = useState(false)
  const [busyAction, setBusyAction] = useState<string | null>(null)
  const [error,      setError]      = useState<string | null>(null)
  const [success,    setSuccess]    = useState<string | null>(null)
  const [publishResults, setPublishResults] = useState<PublishResult[] | null>(null)

  // ── Intake input ──
  const [jobUrl,    setJobUrl]    = useState('')
  const [notes,     setNotes]     = useState('')
  const [notesOpen, setNotesOpen] = useState(false)

  // ── Generation ──
  const [manualMarkdown,  setManualMarkdown]  = useState('')
  const [approvalNotes]   = useState('')
  const [publishTitle,    setPublishTitle]    = useState('')
  const [selectedConns,   setSelectedConns]   = useState<string[]>([])

  // ── Modal ──
  const [markdownModalOpen, setMarkdownModalOpen] = useState(false)

  const requestedJobId = new URLSearchParams(location.search).get('job')
  const requestedProjectId = new URLSearchParams(location.search).get('project')
  const connectedNames = connectors.filter(c => c.status === 'connected').map(c => c.connector_name)
  const googleDocsConnected = connectors.some(
    c => c.connector_name === 'google_docs' && c.status === 'connected'
  )
  const diagramImageCandidates = useMemo(
    () => buildDiagramImageCandidates(output?.doc_flowchart),
    [output?.doc_flowchart]
  )
  const [diagramImageIndex, setDiagramImageIndex] = useState(0)
  const [diagramImageRetryCount, setDiagramImageRetryCount] = useState(0)
  const [diagramImageSrc, setDiagramImageSrc] = useState<string | null>(null)

  // ── Scroll to bottom when new steps appear ──
  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: 'smooth' })
  }, [job?.status, output, busyAction, publishResults])

  // ── Sync output drafts ──
  useEffect(() => {
    setPublishTitle(job ? `Ladder Jobs — ${deriveJobTitle(job)}` : '')
  }, [job])

  // Keep the submitted URL visible during loading; clear only once thread is loaded.
  useEffect(() => {
    if (job?.id) setJobUrl('')
  }, [job?.id])

  // ── Sync selected connectors ──
  useEffect(() => {
    setSelectedConns(prev => {
      const valid = prev.filter(n => connectedNames.includes(n))
      return valid.length > 0 ? valid : connectedNames.slice(0, 1)
    })
  }, [connectedNames.join(',')])

  const diagramCacheKey = `${output?.doc_flowchart?.request_id ?? ''}|${output?.doc_flowchart?.image_url ?? ''}|${Boolean(output?.doc_flowchart?.inline_svg_data_url)}`
  useEffect(() => {
    setDiagramImageIndex(0)
    setDiagramImageRetryCount(0)
    setDiagramImageSrc(diagramImageCandidates[0] ?? null)
  }, [diagramCacheKey])

  const handleDiagramImageError = () => {
    const nextIndex = diagramImageIndex + 1
    if (nextIndex < diagramImageCandidates.length) {
      setDiagramImageIndex(nextIndex)
      setDiagramImageSrc(diagramImageCandidates[nextIndex])
      return
    }
    if (diagramImageRetryCount < 2 && diagramImageCandidates[0]) {
      const base = diagramImageCandidates[0]
      if (base.startsWith('data:')) return
      const separator = base.includes('?') ? '&' : '?'
      setDiagramImageRetryCount(diagramImageRetryCount + 1)
      setDiagramImageSrc(`${base}${separator}cb=${Date.now()}`)
    }
  }

  // ── Load connectors once ──
  useEffect(() => {
    listConnectors().then(r => setConnectors(r.connectors)).catch(() => setConnectors([]))
  }, [])

  // ── Load thread when jobId changes ──
  useEffect(() => {
    const activeId = requestedJobId || getCurrentJobId()
    if (!activeId) {
      setJobId(null); setJob(null); setOutput(null); setRuns([]); setPublishResults(null)
      return
    }
    setCurrentJobId(activeId); setJobId(activeId)

    const loadThread = async () => {
      setLoading(true); setError(null)
      try {
        const [detail, runsRes] = await Promise.all([getJobDetail(activeId), listGenerationRuns(activeId)])
        setJob(detail.job); setOutput(detail.output); setRuns(runsRes.runs)
        setDuplicateNames(detail.duplicates ?? [])
      } catch (e) {
        setError(e instanceof ApiRequestError ? e.message : 'Failed to load thread.')
      } finally {
        setLoading(false)
      }
    }
    void loadThread()
  }, [requestedJobId, location.key])

  const refreshThread = async (id: string) => {
    const [detail, runsRes] = await Promise.all([getJobDetail(id), listGenerationRuns(id)])
    setJob(detail.job); setOutput(detail.output); setRuns(runsRes.runs)
    setDuplicateNames(detail.duplicates ?? [])
  }

  const runAction = async (key: string, fn: () => Promise<void>) => {
    let succeeded = false
    setBusyAction(key); setError(null); setSuccess(null)
    try {
      await fn()
      succeeded = true
    } catch (e) {
      if (e instanceof ApiRequestError) {
        setError(e.message)
        const code = e.payload?.error?.code
        if (code === 'job_not_found') {
          // Stale tab/localStorage thread id: reset to clean workspace state.
          clearCurrentJobId()
          setJobId(null)
          setJob(null)
          setOutput(null)
          setRuns([])
          setPublishResults(null)
          navigate('/workspace')
        }
      } else {
        setError('Unexpected error.')
      }
    } finally {
      if (succeeded) notifyJobsHistoryRefresh()
      setBusyAction(null)
    }
  }

  // ── Intake ──
  const handleIntake = async () => {
    if (!jobUrl.trim()) { setError('Paste a job URL first.'); return }

    // Firecrawl check
    const hasFirecrawl = connectors.some(c => c.connector_name === 'firecrawl' && c.status === 'connected')
    if (!hasFirecrawl) {
      const proceed = window.confirm("Firecrawl is not connected. Job extraction (markdown) will likely fail. Do you want to go to Connectors to set it up? (Cancel to proceed anyway)")
      if (proceed) {
        navigate('/connectors')
        return
      }
    }

    await runAction('intake', async () => {
      const res = await createJobIntake({
        job_url: jobUrl.trim(),
        notes_markdown: notes.trim() || undefined,
        project_id: requestedProjectId ?? undefined,
      })
      const id  = typeof res.job.id === 'string' ? res.job.id : ''
      if (!id) throw new Error('Missing job ID')
      setCurrentJobId(id)
      setNotes(''); setNotesOpen(false)
      
      if (res.job.status !== 'duplicate_notified') {
        try {
          await extractJob(id)
        } catch { } // Error is safely stored on the job record
      }
      navigate(`/workspace?job=${id}`)
    })
  }

  const handleIntakeKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void handleIntake() }
  }

  const handleSaveOutput = async (field: 'proposal_text' | 'google_doc_markdown' | 'loom_script', value: string) => {
    if (!jobId) return
    await runAction(`save-${field}`, async () => {
      const res = await updateJobOutputs(jobId, { [field]: value })
      setOutput(res.output); setSuccess('Saved.')
    })
  }

  const handleRegenerate = async (type: 'proposal' | 'doc' | 'loom_script' | 'workflow', customInstruction?: string) => {
    if (!jobId) return
    await runAction(`regen-${type}`, async () => {
      const instr = customInstruction?.trim() || undefined
      const res = await regenerateOutput(jobId, type, { instruction: instr, queue_if_available: false })
      if (res.output) setOutput(res.output)
      if (res.run)    setRuns(prev => [res.run as GenerationRun, ...prev])
      await refreshThread(jobId)
      setSuccess(res.message)
    })
  }

  // ── Status chips ──
  const jobStatus = typeof job?.status === 'string' ? job.status : 'draft'
  const hasContent = Boolean(job)
  const hasMarkdown = Boolean(job?.job_markdown)
  const hasOutput   = Boolean(output?.proposal_text || output?.google_doc_markdown || output?.loom_script || (output?.workflow_jsons && output.workflow_jsons.length > 0))
  const isApproved  = Boolean(job?.plan_approved)
  const isGenerating = busyAction === 'generate' || busyAction?.startsWith('regen-')

  const isAutomationSupported = !job?.job_type || (
    String(job.job_type).toLowerCase() === 'automation' && 
    (!job.automation_platform || ['n8n', 'make', 'ghl'].includes(String(job.automation_platform).toLowerCase()))
  )

  return (
    <>
      {/* ══ Keyframe styles ══ */}
      <style>{`
        @keyframes bubbleIn {
          from { opacity: 0; transform: translateY(10px) scale(0.97); }
          to   { opacity: 1; transform: translateY(0)   scale(1); }
        }
        @keyframes dotPulse {
          0%, 60%, 100% { opacity: 0.2; transform: scale(0.8); }
          30%            { opacity: 1;   transform: scale(1.15); }
        }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>

      {/* ══ Full-height wrapper ══ */}
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', position: 'relative' }}>

        {/* ══ Thread area ══ */}
        <div
          ref={threadRef}
          style={{
            flex: 1, overflowY: 'auto', padding: '28px 24px',
            display: 'flex', flexDirection: 'column', gap: 16,
            paddingBottom: notesOpen ? 220 : 100,
          }}
        >


          {/* ─── Empty state ─── */}
          {!hasContent && !loading && (
            <div style={{
              flex: 1, display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              minHeight: 'calc(100vh - 240px)', textAlign: 'center', gap: 18,
            }}>
              <div style={{
                width: 72, height: 72, borderRadius: 20,
                background: 'linear-gradient(135deg, rgba(74,222,128,0.15), rgba(74,222,128,0.04))',
                border: '1px solid rgba(74,222,128,0.2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '2rem',
                boxShadow: '0 0 60px rgba(74,222,128,0.1)',
              }}>
                ✦
              </div>
              <div>
                <p className="page-eyebrow" style={{ marginBottom: 6 }}>Workspace</p>
                <h1 style={{
                  fontFamily: '"Space Grotesk", sans-serif', fontSize: 'clamp(1.5rem,3vw,2rem)',
                  fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--on-surface)', marginBottom: 8,
                }}>
                  Start a new job thread
                </h1>
                <p style={{ fontSize: '0.875rem', color: 'var(--on-surface-muted)', maxWidth: 340, lineHeight: 1.65 }}>
                  Paste an Upwork job URL below. We'll extract the job, generate your proposal, and guide you step by step.
                </p>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, justifyContent: 'center' }}>
                {['Intake', 'Extraction', 'Generation', 'Review', 'Publish'].map(step => (
                  <span key={step} className="chip">{step}</span>
                ))}
              </div>
            </div>
          )}

          {/* ─── Loading ─── */}
          {loading && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '20px 0', color: 'var(--on-surface-muted)', fontSize: '0.875rem' }}>
              <span style={{ width: 18, height: 18, border: '2px solid rgba(74,222,128,0.3)', borderTopColor: 'var(--primary)', borderRadius: '50%', display: 'inline-block', animation: 'spin 0.8s linear infinite', flexShrink: 0 }} />
              Loading thread…
            </div>
          )}

          {/* ─── Error / Success banners ─── */}
          {error   && <div className="banner banner-error">{error}</div>}
          {success && <div className="banner banner-success">{success}</div>}

          {/* ════════════════════════════════════════
              THREAD BUBBLES — only when job loaded
          ════════════════════════════════════════ */}
          {hasContent && job && (
            <>
              {/* ── User: intake bubble ── */}
              <Bubble role="user" animateIn>
                <a
                  href={typeof job.job_url === 'string' ? job.job_url : '#'}
                  target="_blank" rel="noreferrer"
                  style={{ fontSize: '0.875rem', color: 'var(--primary)', wordBreak: 'break-all', lineHeight: 1.5 }}
                >
                  {typeof job.job_url === 'string' ? job.job_url : 'Job URL'}
                </a>
                {typeof job.notes_markdown === 'string' && job.notes_markdown.trim() && (
                  <div style={{
                    marginTop: 14, padding: '16px 20px', 
                    background: 'rgba(74,222,128,0.03)',
                    borderRadius: 14, border: '1px solid rgba(74,222,128,0.12)',
                    boxShadow: 'inset 0 1px 1px rgba(255,255,255,0.02)',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 8 }}>
                       <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--primary)' }} />
                       <p style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--primary)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                        Intake Notes & Context
                      </p>
                    </div>
                    <div style={{ 
                      fontSize: '0.875rem', color: 'var(--on-surface-subtle)', 
                      whiteSpace: 'pre-wrap', lineHeight: 1.65,
                      fontFamily: '"Inter", system-ui, sans-serif'
                    }}>
                      {job.notes_markdown}
                    </div>
                  </div>
                )}
              </Bubble>

              {/* ── AI: Job created / extraction ── */}
              <Bubble role="ai" label="Ladder" animateIn>
                <p style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--on-surface)', marginBottom: 6 }}>
                  {hasMarkdown ? 'Job extracted ✓' : 'Thread created — run extraction next'}
                </p>
                {hasMarkdown ? (
                  <>
                    <p style={{ fontSize: '0.8125rem', color: 'var(--on-surface-muted)', marginBottom: 10 }}>
                      {wordCount(job.job_markdown as string)} words extracted
                    </p>
                    <div style={{ position: 'relative', cursor: 'pointer' }} onClick={() => setMarkdownModalOpen(true)}>
                      <pre style={{
                        whiteSpace: 'pre-wrap', fontFamily: 'Inter, system-ui, sans-serif',
                        fontSize: '0.8rem', color: 'var(--on-surface-muted)', lineHeight: 1.65,
                        background: 'rgba(0,0,0,0.2)', padding: '12px 14px', borderRadius: 10,
                        maxHeight: 180, overflowY: 'hidden',
                        position: 'relative',
                        border: '1px solid transparent',
                        transition: 'border-color 150ms',
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'rgba(91,168,160,0.5)' }}
                      onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'transparent' }}
                      >
                        {preview(job.job_markdown as string)}
                        {/* Fade out bottom to indicate scrollable/expandable */}
                        <div style={{
                          position: 'absolute', bottom: 0, left: 0, right: 0, height: 60,
                          background: 'linear-gradient(to top, var(--surface-container), transparent)',
                          pointerEvents: 'none'
                        }} />
                      </pre>
                      <div style={{
                        position: 'absolute', bottom: 10, right: 14,
                        pointerEvents: 'none',
                        background: 'rgba(0,0,0,0.4)', padding: '4px 8px', borderRadius: 6,
                        backdropFilter: 'blur(4px)',
                        fontSize: '0.7rem', color: 'var(--on-surface)', fontWeight: 600,
                      }}>
                        Expand full markdown ↗
                      </div>
                    </div>
                  </>
                ) : job.status === 'duplicate_notified' ? (
                  <>
                    <div style={{
                      padding: '12px', background: 'rgba(255, 193, 7, 0.1)', border: '1px solid rgba(255, 193, 7, 0.3)',
                      borderRadius: '10px', marginBottom: '12px'
                    }}>
                      <p style={{ fontSize: '0.875rem', color: '#D97706', marginBottom: '4px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span>⚠️</span> Duplicate Job Detected
                      </p>
                      <p style={{ fontSize: '0.8125rem', color: 'var(--on-surface-muted)', marginBottom: '12px', lineHeight: 1.5 }}>
                        {duplicateNames.length > 0 ? (
                          <>
                            This job has already been processed by team members:{' '}
                            {duplicateNames.map((name, i) => (
                              <span key={i}>
                                <span style={{ 
                                  color: 'var(--on-surface)', 
                                  fontWeight: 600, 
                                  background: 'rgba(255, 193, 7, 0.2)', 
                                  padding: '2px 6px', 
                                  borderRadius: '4px',
                                  margin: '0 2px' 
                                }}>
                                  {name}
                                </span>
                                {i < duplicateNames.length - 1 ? ', ' : '.'}
                              </span>
                            ))}
                          </>
                        ) : 'This job was already processed by another teammate.'}
                      </p>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button
                          type="button"
                          className="btn btn-sm"
                          style={{
                            background: 'rgba(239, 68, 68, 0.1)', color: '#EF4444', border: '1px solid rgba(239, 68, 68, 0.2)',
                            borderRadius: '100px', fontWeight: 500, padding: '4px 14px', cursor: 'pointer'
                          }}
                          disabled={busyAction !== null}
                          onClick={() => runAction('duplicateStop', async () => {
                            if (!jobId) return;
                            await sendDuplicateDecision(jobId, 'stop');
                            await refreshThread(jobId);
                          })}
                        >
                          {busyAction === 'duplicateStop' ? 'Closing...' : 'Close Job'}
                        </button>
                        <button
                          type="button"
                          className="btn btn-sm btn-primary btn-pill"
                          disabled={busyAction !== null}
                          onClick={() => runAction('duplicateContinue', async () => {
                            if (!jobId) return;
                            await sendDuplicateDecision(jobId, 'continue');
                            try {
                              await extractJob(jobId);
                            } catch { }
                            await refreshThread(jobId);
                          })}
                        >
                          {busyAction === 'duplicateContinue' ? 'Scraping...' : 'Continue & Scrape'}
                        </button>
                      </div>
                    </div>
                  </>
                ) : (
                  <>
                    {typeof job.extraction_error === 'string' && job.extraction_error.trim() && (
                      <p style={{ fontSize: '0.8125rem', color: 'var(--danger)', marginBottom: 8 }}>
                        ⚠ {job.extraction_error}
                      </p>
                    )}
                    <button
                      type="button"
                      disabled={busyAction !== null}
                      className="btn btn-sm btn-primary btn-pill"
                      onClick={() => runAction('extract', async () => {
                        if (!jobId) return
                        const res = await extractJob(jobId)
                        setJob(res.job)
                        await refreshThread(jobId)
                        setSuccess(res.message)
                      })}
                    >
                      {busyAction === 'extract' ? 'Extracting…' : 'Run extraction →'}
                    </button>
                  </>
                )}

                {/* Manual markdown fallback */}
                {job.requires_manual_markdown && !hasMarkdown && (
                  <div style={{
                    marginTop: 14, padding: '14px 16px', borderRadius: 12,
                    background: 'rgba(251,191,36,0.06)', border: '1px solid rgba(251,191,36,0.2)',
                  }}>
                    <p style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--warning)', marginBottom: 8 }}>
                      Manual markdown required
                    </p>
                    <textarea
                      rows={5}
                      value={manualMarkdown}
                      onChange={e => setManualMarkdown(e.target.value)}
                      placeholder="Paste clean job markdown here."
                      style={{
                        width: '100%', background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.08)',
                        borderRadius: 10, padding: '10px 12px', color: 'var(--on-surface)',
                        fontSize: '0.8125rem', lineHeight: 1.65, resize: 'vertical', outline: 'none',
                      }}
                    />
                    <button
                      type="button"
                      disabled={busyAction !== null || manualMarkdown.trim().length < 20}
                      className="btn btn-sm btn-primary btn-pill"
                      style={{ marginTop: 8 }}
                      onClick={() => runAction('manual-md', async () => {
                        if (!jobId) return
                        const res = await saveManualMarkdown(jobId, manualMarkdown.trim())
                        setJob(res.job); setManualMarkdown('')
                        await refreshThread(jobId); setSuccess(res.message)
                      })}
                    >
                      Save markdown
                    </button>
                  </div>
                )}
              </Bubble>

              {/* ── AI: Generation step — shows after extraction ── */}
              {hasMarkdown && (
                <Bubble role="ai" label="Ladder" accent animateIn>
                  {/* Job Explanation Panel */}
                  <div style={{
                    background: 'var(--surface-container)',
                    border: '1px solid var(--border)',
                    borderRadius: 16,
                    overflow: 'hidden',
                    marginBottom: 20,
                    boxShadow: '0 4px 24px rgba(0,0,0,0.2)',
                  }}>
                    <div style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '12px 20px', borderBottom: '1px solid var(--border)', background: 'rgba(255,255,255,0.02)'
                    }}>
                      <h3 style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--on-surface)' }}>Job Explanation</h3>
                      <button
                        type="button"
                        disabled={busyAction !== null}
                        onClick={() => runAction('explain', async () => {
                          if (!jobId) return
                          const res = await explainJob(jobId)
                          setJob(res.job)
                          setSuccess('Job explanation regenerated.')
                        })}
                        className="btn btn-sm btn-ghost btn-pill"
                        style={{ color: 'var(--primary)', borderColor: 'var(--border-accent)', background: 'var(--primary-glow)' }}
                      >
                        {busyAction === 'explain' ? 'Regenerating…' : '✦ Regenerate'}
                      </button>
                    </div>
                    <div style={job?.job_explanation ? { padding: '20px 24px', maxHeight: 400, overflowY: 'auto' } : { padding: '20px 24px' }}>
                      {typeof job?.job_explanation === 'string' && job.job_explanation.trim() ? (
                        <div className="doc-preview">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {job.job_explanation}
                          </ReactMarkdown>
                        </div>
                      ) : (
                        <div style={{ color: 'var(--on-surface-muted)', fontSize: '0.875rem' }}>
                          <p>Explanation not available.</p>
                        </div>
                      )}
                    </div>
                    {/* Initial Generate Buttons Footer */}
                    {!hasOutput && (
                      <div style={{
                        padding: '16px 20px', borderTop: '1px solid var(--border)', background: 'rgba(255,255,255,0.01)',
                        display: 'flex', gap: 12, alignItems: 'center'
                      }}>
                        {isGenerating ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                            <ThinkingDots />
                            <span style={{ fontSize: '0.875rem', color: 'var(--primary)' }}>Generating outputs…</span>
                          </div>
                        ) : (
                          <>
                            <button
                              type="button"
                              disabled={busyAction !== null}
                              className="btn btn-primary btn-pill"
                              onClick={() => handleRegenerate(isAutomationSupported ? 'workflow' : 'doc')}
                            >
                              {isAutomationSupported ? `Generate ${getPlatformName(job?.automation_platform)} Workflow →` : 'Generate Google Doc →'}
                            </button>
                            <span style={{ fontSize: '0.8125rem', color: 'var(--on-surface-muted)', marginLeft: 8 }}>
                              {isAutomationSupported ? 'Based on job details and intake notes.' : 'Generate an initial project proposal doc.'}
                            </span>
                          </>
                        )}
                      </div>
                    )}
                  </div>

                  {hasOutput && (
                    <>
                      <>
                        {(output?.workflow_jsons?.length ?? 0) > 0 && output && (
                          <OutputArtifactView 
                            type="workflow" 
                            label={`${getPlatformName(job?.automation_platform)} Workflow`}
                            content={JSON.stringify(output.workflow_jsons.length === 1 ? output.workflow_jsons[0].workflow_json : output.workflow_jsons.map(w => w.workflow_json), null, 2)}
                            field={null} 
                            busyAction={busyAction} 
                            onSave={handleSaveOutput} 
                            onRegenerate={handleRegenerate} 
                          />
                        )}
                        {output?.google_doc_markdown && (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                            <OutputArtifactView type="doc" label="Doc" content={output.google_doc_markdown} field="google_doc_markdown" busyAction={busyAction} onSave={handleSaveOutput} onRegenerate={handleRegenerate} />
                            
                            {/* Diagram Panel */}
                            <div style={{
                              background: 'var(--surface-container)',
                              border: '1px solid var(--border)',
                              borderRadius: 16,
                              overflow: 'hidden',
                              marginBottom: 20,
                              boxShadow: '0 4px 24px rgba(0,0,0,0.2)',
                            }}>
                              <div style={{ padding: '12px 20px', borderBottom: '1px solid var(--border)', background: 'rgba(255,255,255,0.02)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                <h3 style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--on-surface)' }}>Doc Diagram</h3>
                                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                                  {output.doc_flowchart?.status === 'ready' && (
                                    <span style={{ fontSize: '0.75rem', color: 'var(--primary)', padding: '2px 8px', borderRadius: 12, background: 'rgba(91,168,160,0.1)' }}>Ready</span>
                                  )}
                                  {output.doc_flowchart?.quality_status && (
                                    <span
                                      style={{
                                        fontSize: '0.72rem',
                                        color: (output.doc_flowchart?.quality_status ?? '').includes('passed') ? 'var(--primary)' : '#fca5a5',
                                        padding: '2px 8px',
                                        borderRadius: 12,
                                        background: (output.doc_flowchart?.quality_status ?? '').includes('passed')
                                          ? 'rgba(91,168,160,0.1)'
                                          : 'rgba(239, 68, 68, 0.08)',
                                      }}
                                    >
                                      {output.doc_flowchart?.quality_status}
                                    </span>
                                  )}
                                </div>
                              </div>
                              <div style={{ padding: '20px 24px' }}>
                                {diagramImageSrc || output.doc_flowchart?.image_url ? (
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                                    <div style={{ background: '#fff', padding: 8, borderRadius: 8 }}>
                                      <img
                                        src={diagramImageSrc || output.doc_flowchart?.image_url || ''}
                                        alt="Doc Diagram"
                                        style={{ width: '100%', borderRadius: 4 }}
                                        referrerPolicy="no-referrer"
                                        loading="eager"
                                        onError={handleDiagramImageError}
                                      />
                                    </div>
                                    <a
                                      href={output.doc_flowchart?.image_url ?? '#'}
                                      target="_blank"
                                      rel="noreferrer"
                                      style={{ fontSize: '0.78rem', color: 'var(--primary)' }}
                                    >
                                      Open diagram image in new tab
                                    </a>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, fontSize: '0.8rem', color: 'var(--on-surface-muted)', marginTop: 8 }}>
                                      <span title="Words analyzed from the document context used to build the diagram">
                                        Words analyzed: <strong style={{ color: 'var(--on-surface)' }}>{output.doc_flowchart?.words_sent ?? 0}</strong>
                                      </span>
                                      <span title="Horizontal layout family selected by the diagram generator">
                                        Layout: <strong style={{ color: 'var(--on-surface)' }}>{output.doc_flowchart?.layout_family ?? 'roadmap_cards'}</strong>
                                      </span>
                                      <span title="Diagram orientation used for Google Docs embedding">
                                        Orientation: <strong style={{ color: 'var(--on-surface)' }}>{output.doc_flowchart?.orientation ?? 'horizontal'}</strong>
                                      </span>
                                      <span title="Creativity level selected for the generated visual style">
                                        Creativity: <strong style={{ color: 'var(--on-surface)' }}>{output.doc_flowchart?.creativity_level ?? 'medium'}</strong>
                                      </span>
                                      <span title="Connection routing style used to render the flowchart">
                                        Connections: <strong style={{ color: 'var(--on-surface)' }}>{output.doc_flowchart?.connection_style ?? 'clean'}</strong>
                                      </span>
                                      <span title="Quality score from deterministic diagram validator">
                                        Quality: <strong style={{ color: 'var(--on-surface)' }}>{Math.round(output.doc_flowchart?.quality_score ?? 0)}</strong>
                                      </span>
                                    </div>
                                    {(output.doc_flowchart?.validation_errors?.length ?? 0) > 0 && (
                                      <p style={{ color: '#fca5a5', fontSize: '0.78rem', marginTop: 4 }}>
                                        Validation: {output.doc_flowchart?.validation_errors?.join(', ')}
                                      </p>
                                    )}
                                    {output.doc_flowchart?.error && <p style={{ color: 'var(--danger)', fontSize: '0.8rem', marginTop: 4 }}>Error: {output.doc_flowchart?.error}</p>}
                                  </div>
                                ) : (
                                  <div style={{ fontSize: '0.875rem', color: 'var(--on-surface-muted)' }}>
                                    {!googleDocsConnected ? (
                                      <p style={{ color: '#fca5a5' }}>Google Docs connector is not set up. Diagram generation requires it to stage the image. <button onClick={() => navigate('/connectors')} style={{ background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer', textDecoration: 'underline', fontSize: 'inherit', padding: 0 }}>Fix now</button></p>
                                    ) : output.doc_flowchart?.error ? (
                                      <p style={{ color: 'var(--danger)' }}>{output.doc_flowchart.error}</p>
                                    ) : (
                                      <p>Generate a horizontal diagram from full document context: problem, approach, implementation, and solution flow.</p>
                                    )}
                                  </div>
                                )}
                              </div>
                              <div style={{
                                padding: '12px 20px', borderTop: '1px solid var(--border)', background: 'rgba(255,255,255,0.01)',
                                display: 'flex', gap: 12, alignItems: 'center'
                              }}>
                                <input 
                                  className="input" 
                                  type="text"
                                  id="flowchart-instruction-input"
                                  placeholder="Regenerate instructions (optional). Example: emphasize implementation decisions."
                                  style={{ flex: 1, height: 36, fontSize: '0.8125rem', background: 'rgba(0,0,0,0.2)' }}
                                />
                                <button
                                  type="button"
                                  disabled={busyAction !== null || !output.google_doc_markdown?.trim() || !googleDocsConnected}
                                  className="btn btn-sm btn-ghost btn-pill"
                                  style={{ 
                                    color: 'var(--primary)', 
                                    borderColor: 'var(--border-accent)', 
                                    background: 'var(--primary-glow)',
                                    opacity: (!output.google_doc_markdown?.trim() || !googleDocsConnected) ? 0.5 : 1
                                  }}
                                  onClick={() => {
                                    const input = document.getElementById('flowchart-instruction-input') as HTMLInputElement;
                                    runAction('generate-flowchart', async () => {
                                      if (!jobId) return;
                                      const res = await generateDocFlowchart(jobId, { instruction: input.value, connection_style: 'clean' });
                                      setOutput(res.output);
                                      setSuccess('Diagram generated successfully.');
                                      input.value = '';
                                    });
                                  }}
                                >
                                  {busyAction === 'generate-flowchart'
                                    ? 'Generating...'
                                    : output.doc_flowchart?.image_url
                                      ? 'Regenerate Diagram'
                                      : 'Generate Diagram'}
                                </button>
                              </div>
                            </div>
                          </div>
                        )}
                        {output?.loom_script && (
                          <OutputArtifactView type="loom_script" label="Loom Script" content={output.loom_script} field="loom_script" busyAction={busyAction} onSave={handleSaveOutput} onRegenerate={handleRegenerate} />
                        )}
                        {output?.proposal_text && (
                          <OutputArtifactView type="proposal" label="Proposal" content={output.proposal_text} field="proposal_text" busyAction={busyAction} onSave={handleSaveOutput} onRegenerate={handleRegenerate} />
                        )}

                        {/* Strict Linear Waterfall Generation Buttons */}
                        <div style={{ marginTop: 24, display: 'flex', flexWrap: 'wrap', gap: 12 }}>
                          {/* Step 2: Doc (after workflow) */}
                          {((output?.workflow_jsons?.length ?? 0) > 0 || !isAutomationSupported) && !output?.google_doc_markdown && (
                            <button
                              type="button"
                              disabled={busyAction !== null}
                              className="btn btn-primary btn-pill"
                              onClick={() => handleRegenerate('doc')}
                            >
                              {busyAction === 'regen-doc' ? 'Generating Doc…' : '✦ Generate Google Doc →'}
                            </button>
                          )}

                          {/* Step 3: Loom Script (after doc) */}
                          {output?.google_doc_markdown && !output?.loom_script && (
                            <button
                              type="button"
                              disabled={busyAction !== null}
                              className="btn btn-primary btn-pill"
                              onClick={() => handleRegenerate('loom_script')}
                            >
                              {busyAction === 'regen-loom_script' ? 'Generating Loom Script…' : '✦ Generate Loom Script →'}
                            </button>
                          )}

                          {/* Step 4: Proposal (after loom script) */}
                          {output?.loom_script && !output?.proposal_text && (
                            <button
                              type="button"
                              disabled={busyAction !== null}
                              className="btn btn-primary btn-pill"
                              onClick={() => handleRegenerate('proposal')}
                            >
                              {busyAction === 'regen-proposal' ? 'Generating Proposal…' : '✦ Generate Proposal →'}
                            </button>
                          )}
                        </div>
                      </>
                      {!isApproved && (
                        <div style={{ marginTop: 14, display: 'flex', gap: 8, flexWrap: 'wrap', borderTop: '1px solid var(--border)', paddingTop: 16 }}>
                          <button type="button" disabled={busyAction !== null} className="btn btn-sm btn-ghost btn-pill"
                            onClick={() => runAction('approve', async () => {
                              if (!jobId) return
                              const res = await approveJob(jobId, approvalNotes.trim() || undefined)
                              setJob(res.job); setOutput(res.output); setSuccess(res.message)
                            })}
                          >
                            {busyAction === 'approve' ? 'Approving…' : 'Approve outputs'}
                          </button>
                          <p style={{ fontSize: '0.78rem', color: 'var(--on-surface-muted)', alignSelf: 'center' }}>
                            Publish options are visible below; approval enables the Publish button.
                          </p>
                        </div>
                      )}
                      {(
                        <div style={{ marginTop: 14 }}>
                          <p style={{ fontSize: '0.75rem', color: isApproved ? 'var(--primary)' : 'var(--on-surface-muted)', fontWeight: 600, marginBottom: 8 }}>
                            {isApproved ? '✓ Approved — ready to publish' : 'Approve outputs to publish'}
                          </p>
                          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                            {connectedNames.map(name => (
                              <label key={name} style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: '0.8125rem', color: 'var(--on-surface-muted)' }}>
                                <input
                                  type="checkbox"
                                  checked={selectedConns.includes(name)}
                                  onChange={e => setSelectedConns(prev => e.target.checked ? [...prev, name] : prev.filter(n => n !== name))}
                                  style={{ accentColor: 'var(--primary)' }}
                                />
                                {name}
                              </label>
                            ))}
                            {connectedNames.length === 0 && (
                              <p style={{ fontSize: '0.8125rem', color: 'var(--on-surface-muted)' }}>No connected destinations.</p>
                            )}
                            {!connectedNames.includes('google_docs') && (
                              <p style={{ fontSize: '0.75rem', color: '#fca5a5' }}>
                                ⚠️ Google Docs not connected. 
                                <button onClick={() => navigate('/connectors')} style={{ background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer', textDecoration: 'underline', fontSize: 'inherit', padding: '0 4px' }}>Setup</button>
                                to publish rich docs.
                              </p>
                            )}
                            <button
                              type="button"
                              disabled={busyAction !== null || selectedConns.length === 0 || !isApproved}
                              className="btn btn-sm btn-primary btn-pill"
                              onClick={() => runAction('publish', async () => {
                                if (!jobId) return
                                const popup = window.open('', '_blank')
                                if (popup) {
                                  popup.document.title = 'Publishing...'
                                  popup.document.body.innerHTML = '<p style="font-family: sans-serif; padding: 24px;">Preparing your Google Doc...</p>'
                                }
                                const res = await publishJob(jobId, { connectors: selectedConns, title: publishTitle.trim() || undefined })
                                await refreshThread(jobId)
                                setPublishResults(res.results)
                                setSuccess(`Published to ${res.results.map(r => r.connector_name).join(', ')}.`)

                                const docsResult = res.results.find(r => r.connector_name === 'google_docs')
                                if (docsResult?.status === 'published') {
                                  try {
                                    const directUrl = docsResult.external_url || res.google_doc_open_url || res.google_doc_url
                                    if (directUrl) {
                                      if (popup && !popup.closed) {
                                        popup.location.assign(directUrl)
                                      } else {
                                        const anchor = document.createElement('a')
                                        anchor.href = directUrl
                                        anchor.target = '_blank'
                                        anchor.rel = 'noopener noreferrer'
                                        anchor.click()
                                      }
                                      return
                                    }
                                    const outputs = await getJobOutputs(jobId)
                                    if (outputs.output.google_doc_url) {
                                      if (popup && !popup.closed) {
                                        popup.location.assign(outputs.output.google_doc_url)
                                      } else {
                                        const anchor = document.createElement('a')
                                        anchor.href = outputs.output.google_doc_url
                                        anchor.target = '_blank'
                                        anchor.rel = 'noopener noreferrer'
                                        anchor.click()
                                      }
                                      return
                                    }
                                    if (popup) popup.close()
                                  } catch (e) {
                                    if (popup) popup.close()
                                    console.error('Failed to open doc auto URL', e)
                                  }
                                } else if (popup) {
                                  popup.close()
                                }
                              })}
                            >
                              {busyAction === 'publish'
                                ? 'Publishing…'
                                : isApproved
                                  ? 'Publish →'
                                  : 'Approve first to publish'}
                            </button>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </Bubble>
              )}

              {/* ── Publish results bubble ── */}
              {publishResults && (
                <Bubble role="system" label="Published" animateIn>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {publishResults.map(r => (
                      <div key={r.connector_name} style={{ display: 'flex', flexDirection: 'column', gap: 4, padding: '8px 12px', background: 'rgba(255,255,255,0.03)', borderRadius: 10, border: '1px solid var(--border)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: '0.875rem' }}>
                          <span style={{ color: r.status === 'published' ? 'var(--primary)' : 'var(--danger)' }}>
                            {r.status === 'published' ? 'Published' : 'Failed'}
                          </span>
                          <span style={{ fontWeight: 600, color: 'var(--on-surface)' }}>{r.connector_name}</span>
                          {r.message && <span style={{ color: 'var(--on-surface-muted)', fontSize: '0.8rem' }}>— {r.message}</span>}
                        </div>
                        
                        {r.connector_name === 'google_docs' && r.metadata && (
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginLeft: 26, marginTop: 2 }}>
                            {r.metadata.diagram_included !== undefined && (
                              <span style={{ 
                                fontSize: '0.75rem', 
                                padding: '2px 8px', 
                                borderRadius: 12, 
                                background: r.metadata.diagram_included ? 'rgba(91,168,160,0.1)' : 'rgba(239, 68, 68, 0.05)',
                                color: r.metadata.diagram_included ? 'var(--primary)' : 'var(--danger)',
                                border: `1px solid ${r.metadata.diagram_included ? 'rgba(91,168,160,0.2)' : 'rgba(239, 68, 68, 0.1)'}`
                              }}>
                                {r.metadata.diagram_included ? '⚡ Diagram Embedded' : `⚠️ Diagram Skipped: ${r.metadata.diagram_reason || 'Unknown'}`}
                              </span>
                            )}
                            {r.metadata.flowchart_section_removed && (
                              <span style={{ 
                                fontSize: '0.75rem', 
                                padding: '2px 8px', 
                                borderRadius: 12, 
                                background: 'rgba(255,255,255,0.05)',
                                color: 'var(--on-surface-muted)',
                                border: '1px solid var(--border)'
                              }}>
                                ✨ Content Optimized (Duplicate text removed)
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </Bubble>
              )}

              {/* ── Application Tracking (always visible once job loaded) ── */}
              <Bubble role="system" label="Application Tracking">
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
                  {/* Sent / Not Sent toggle */}
                  <button
                    type="button"
                    disabled={busyAction !== null}
                    onClick={() => runAction('sub-track', async () => {
                      if (!jobId) return
                      const nowSent = !(job.is_submitted_to_upwork ?? false)
                      const res = await updateJobSubmission(jobId, {
                        is_submitted_to_upwork: nowSent,
                        submitted_at: nowSent ? new Date().toISOString() : null,
                      })
                      setJob(res.job)
                      setSuccess(res.job.is_submitted_to_upwork ? '✅ Marked as Sent to Upwork' : 'Marked as Not Sent.')
                    })}
                    style={(() => {
                      const isSent = job.is_submitted_to_upwork ?? false
                      return {
                        display: 'inline-flex', alignItems: 'center', gap: 8,
                        height: 34, padding: '0 16px', borderRadius: 999,
                        fontSize: '0.8125rem', fontWeight: 600,
                        cursor: busyAction !== null ? 'not-allowed' : 'pointer',
                        transition: 'all 180ms',
                        background: isSent ? 'rgba(74,222,128,0.12)' : 'rgba(255,255,255,0.04)',
                        color: isSent ? 'var(--primary)' : 'var(--on-surface-muted)',
                        border: `1px solid ${isSent ? 'rgba(74,222,128,0.35)' : 'var(--border)'}`,
                        opacity: busyAction !== null ? 0.55 : 1,
                      }
                    })()}
                  >
                    {(() => {
                      const isSent = job.is_submitted_to_upwork ?? false
                      return (
                        <>
                          <span style={{
                            width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                            background: isSent ? 'var(--primary)' : 'var(--on-surface-subtle)',
                            boxShadow: isSent ? '0 0 6px var(--primary)' : undefined,
                            transition: 'all 180ms',
                          }} />
                          {busyAction === 'sub-track'
                            ? 'Updating…'
                            : isSent
                              ? '✅ Sent to Upwork'
                              : '📤 Not Sent Yet'
                          }
                        </>
                      )
                    })()}
                  </button>

                  {/* Outcome dropdown */}
                  <select
                    className="input"
                    value={job.outcome || ''}
                    onChange={(e) => runAction('outcome', async () => {
                      if (!jobId) return
                      const val = e.target.value as JobOutcome
                      const res = await updateJobStatusOutcome(jobId, { outcome: val || null })
                      setJob(res.job)
                      setSuccess(val ? `Outcome: ${readableLabel(val)}` : 'Outcome cleared.')
                    })}
                    style={{ height: 34, fontSize: '0.8125rem', padding: '0 32px 0 12px', minWidth: 150, borderRadius: 10 }}
                    disabled={busyAction !== null}
                  >
                    <option value="">Outcome: Unknown</option>
                    <option value="sent">📤 Sent</option>
                    <option value="not_sent">🚫 Not sent</option>
                    <option value="hired">✅ Hired</option>
                  </select>
                </div>
              </Bubble>

              {/* ── Status row ── */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingLeft: 38, flexWrap: 'wrap' }}>
                <span className={`chip${jobStatus === 'ready' || jobStatus === 'approved' ? ' chip-active' : ''}`}>
                  {readableLabel(jobStatus)}
                </span>
                {runs.length > 0 && (
                  <span className="chip">{runs.length} run{runs.length > 1 ? 's' : ''}</span>
                )}
                <button
                  type="button"
                  className="btn btn-sm btn-ghost btn-pill"
                  onClick={() => {
                    clearCurrentJobId(); setJobId(null); setJob(null)
                    setOutput(null); setRuns([]); setPublishResults(null)
                    navigate('/workspace')
                  }}
                >
                  + New thread
                </button>
              </div>
            </>
          )}
        </div>

        <div style={{
          position: 'sticky', bottom: 0, left: 0, right: 0,
          padding: '12px 20px 16px',
          background: 'linear-gradient(to top, var(--surface) 70%, transparent)',
          zIndex: 10,
        }}>
          {/* Firecrawl Warning */}
          {!hasContent && !connectors.some(c => c.connector_name === 'firecrawl' && c.status === 'connected') && (
            <div style={{
              maxWidth: 720, margin: '0 auto 8px',
              padding: '8px 14px',
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.2)',
              borderRadius: 12,
              fontSize: '0.85rem',
              color: '#fca5a5',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
            }}>
              <span style={{ fontSize: '1rem' }}>⚠️</span>
              <span style={{ flex: 1 }}>
                Firecrawl is not connected. Job extraction will fail. 
                <button 
                  onClick={() => navigate('/connectors')} 
                  style={{ 
                    background: 'none', border: 'none', color: 'var(--primary)', 
                    cursor: 'pointer', textDecoration: 'underline', padding: '0 4px',
                    fontWeight: 600
                  }}
                >
                  Setup Connectors
                </button>
              </span>
            </div>
          )}

          {/* Notes expander (only on intake / no job) */}
          {notesOpen && !hasContent && (
            <div style={{ maxWidth: 720, margin: '0 auto 8px' }}>
              <textarea
                autoFocus
                rows={4}
                className="input"
                value={notes}
                onChange={e => setNotes(e.target.value)}
                placeholder="Add context: proof points, tone, budget, delivery constraints…"
                style={{ borderRadius: 12, resize: 'none' }}
              />
            </div>
          )}

          {/* Main input row */}
          {!hasContent && (
            <div style={{
              maxWidth: 720, margin: '0 auto',
              display: 'flex', gap: 8, alignItems: 'center',
              background: 'var(--surface-container)',
              border: '1px solid var(--border)',
              borderRadius: 16,
              padding: '6px 10px 6px 16px',
              boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
              transition: 'border-color 200ms',
            }}>
              {/* Notes toggle */}
              <button
                type="button"
                onClick={() => setNotesOpen(v => !v)}
                title="Add notes"
                style={{
                  flexShrink: 0, width: 30, height: 30, borderRadius: 8,
                  background: notesOpen ? 'var(--primary-glow)' : 'none',
                  border: `1px solid ${notesOpen ? 'var(--border-accent)' : 'transparent'}`,
                  cursor: 'pointer', color: notesOpen ? 'var(--primary)' : 'var(--on-surface-muted)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  transition: 'all 150ms',
                }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
                  <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
                </svg>
              </button>

              <input
                type="text"
                value={jobUrl}
                onChange={e => setJobUrl(e.target.value)}
                onKeyDown={handleIntakeKey}
                placeholder="Paste Upwork job URL and press Enter…"
                style={{
                  flex: 1, background: 'none', border: 'none', outline: 'none',
                  color: 'var(--on-surface)', fontSize: '0.9rem',
                  lineHeight: 1, height: 36,
                }}
              />

              <button
                type="button"
                disabled={busyAction !== null || !jobUrl.trim()}
                onClick={handleIntake}
                style={{
                  flexShrink: 0, width: 36, height: 36, borderRadius: 10,
                  background: jobUrl.trim() ? 'var(--primary)' : 'rgba(74,222,128,0.1)',
                  border: 'none', cursor: jobUrl.trim() ? 'pointer' : 'default',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  transition: 'background 150ms',
                }}
              >
                {busyAction === 'intake' ? (
                  <span style={{ width: 16, height: 16, border: '2px solid rgba(0,0,0,0.3)', borderTopColor: 'var(--on-primary)', borderRadius: '50%', display: 'inline-block', animation: 'spin 0.8s linear infinite' }} />
                ) : (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={jobUrl.trim() ? 'var(--on-primary)' : 'var(--primary)'} strokeWidth="2.5" strokeLinecap="round">
                    <line x1="22" y1="2" x2="11" y2="13" />
                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                )}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ══ Extracted Markdown Modal ══ */}
      {markdownModalOpen && job && job.job_markdown && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 100,
          background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: '24px'
        }}>
          <div style={{
            background: 'var(--surface)', borderRadius: 20,
            border: '1px solid var(--border-accent)',
            width: '100%', maxWidth: 860, maxHeight: 'calc(100vh - 48px)',
            display: 'flex', flexDirection: 'column',
            boxShadow: '0 20px 60px rgba(0,0,0,0.4)'
          }}>
            <header style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '16px 24px', borderBottom: '1px solid var(--border)',
              background: 'rgba(255,255,255,0.02)'
            }}>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--on-surface)' }}>
                Extracted Job Markdown
              </h2>
              <button
                onClick={() => setMarkdownModalOpen(false)}
                className="btn btn-ghost"
                style={{ width: 32, height: 32, padding: 0, borderRadius: '50%' }}
              >
                ✕
              </button>
            </header>
            <div style={{
              flex: 1, overflowY: 'auto', padding: '24px',
              fontSize: '0.875rem', lineHeight: 1.7, color: 'var(--on-surface)',
              fontFamily: 'Inter, system-ui, sans-serif'
            }}>
              <pre style={{
                whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                margin: 0
              }}>
                {job.job_markdown}
              </pre>
            </div>
          </div>
        </div>
      )}


    </>
  )
}


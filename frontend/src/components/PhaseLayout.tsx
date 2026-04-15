import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  ApiRequestError,
  createProject,
  deleteJob,
  deleteProject,
  getMe,
  listJobs,
  listProjects,
  renameProject,
  updateJobProject,
  type AuthUser,
  type JobRecord,
  type ProjectRecord,
} from '../lib/api'
import { clearCurrentJobId, getCurrentJobId, setCurrentJobId } from '../lib/currentJob'
import { JOBS_HISTORY_REFRESH_EVENT } from '../lib/events'
import { deriveJobTitle } from '../lib/jobTitles'

/* ─── Icons ─── */
const IconMenu = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <line x1="4" y1="6" x2="20" y2="6" />
    <line x1="4" y1="12" x2="20" y2="12" />
    <line x1="4" y1="18" x2="20" y2="18" />
  </svg>
)
const IconPlus = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
)
const IconLink = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
    <path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71" />
    <path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71" />
  </svg>
)
const IconChart = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
    <path d="M18 20V10" />
    <path d="M12 20V4" />
    <path d="M6 20v-4" />
  </svg>
)

const IconDashboard = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
    <rect x="3" y="3" width="7" height="9" rx="1" />
    <rect x="14" y="3" width="7" height="5" rx="1" />
    <rect x="14" y="12" width="7" height="9" rx="1" />
    <rect x="3" y="16" width="7" height="5" rx="1" />
  </svg>
)


/* ─── Date grouping ─── */
function groupJobs(jobs: JobRecord[]) {
  const now = new Date()
  now.setHours(0, 0, 0, 0)
  const day = 86_400_000
  const todayStart = now.getTime()
  const yestStart  = todayStart - day
  const weekStart  = todayStart - 6 * day

  const today: JobRecord[] = [], yesterday: JobRecord[] = [], week: JobRecord[] = [], older: JobRecord[] = []
  for (const job of jobs) {
    const ts = typeof job.created_at === 'string' ? Date.parse(job.created_at) : Number.NaN
    if (Number.isNaN(ts)) older.push(job)
    else if (ts >= todayStart) today.push(job)
    else if (ts >= yestStart) yesterday.push(job)
    else if (ts >= weekStart) week.push(job)
    else older.push(job)
  }
  return { today, yesterday, week, older }
}

/* ─── History group ─── */
function HistGroup({
  label, jobs, active, projects, onSelect, onDelete, onAssignProject,
}: {
  label: string
  jobs: JobRecord[]
  active: string | null
  projects: ProjectRecord[]
  onSelect: (id: string) => void
  onDelete: (id: string) => void
  onAssignProject: (jobId: string, projectId: string | null) => Promise<void>
}) {
  if (!jobs.length) return null
  return (
    <div style={{ marginTop: 14 }}>
      <div className="section-label" style={{ marginBottom: 4 }}>{label}</div>
      {jobs.map((job) => {
        const id = job.id as string
        const isActive = active === id
        return (
          <HistItem
            key={id}
            job={job}
            isActive={isActive}
            projects={projects}
            onSelect={onSelect}
            onDelete={onDelete}
            onAssignProject={onAssignProject}
          />
        )
      })}
    </div>
  )
}

/* ─── Single history item with three-dot delete ─── */
function HistItem({
  job, isActive, projects, onSelect, onDelete, onAssignProject,
}: {
  job: JobRecord
  isActive: boolean
  projects: ProjectRecord[]
  onSelect: (id: string) => void
  onDelete: (id: string) => void
  onAssignProject: (jobId: string, projectId: string | null) => Promise<void>
}) {
  const [hovered, setHovered] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [assigning, setAssigning] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const id = job.id as string
  const title = deriveJobTitle(job)
  const currentProjectId = typeof job.project_id === 'string' ? job.project_id : null

  // Close menu on outside click
  useEffect(() => {
    if (!menuOpen) return
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [menuOpen])

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation()
    setMenuOpen(false)
    setDeleting(true)
    try {
      await deleteJob(id)
      onDelete(id)
    } catch {
      setDeleting(false)
    }
  }

  const handleAssignProject = async (e: React.MouseEvent, projectId: string | null) => {
    e.stopPropagation()
    if (assigning || deleting) return
    setAssigning(true)
    try {
      await onAssignProject(id, projectId)
      setMenuOpen(false)
    } finally {
      setAssigning(false)
    }
  }

  return (
    <div
      style={{ position: 'relative', display: 'flex', alignItems: 'center' }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => { setHovered(false); setMenuOpen(false) }}
    >
      <button
        type="button"
        onClick={() => onSelect(id)}
        className={`history-item${isActive ? ' active' : ''}`}
        title={title}
        style={{
          flex: 1,
          opacity: deleting || assigning ? 0.4 : 1,
          paddingRight: 28,
          pointerEvents: deleting || assigning ? 'none' : undefined,
        }}
      >
        <span className="history-dot" />
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
          {title}
        </span>
      </button>

      {/* Three-dot button — visible on hover */}
      {(hovered || menuOpen) && !deleting && (
        <div ref={menuRef} style={{ position: 'absolute', right: 4, top: '50%', transform: 'translateY(-50%)', zIndex: 20 }}>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); setMenuOpen(v => !v) }}
            title="More options"
            style={{
              width: 24, height: 24, borderRadius: 6,
              background: menuOpen ? 'rgba(255,255,255,0.1)' : 'rgba(255,255,255,0.06)',
              border: '1px solid rgba(255,255,255,0.08)',
              cursor: 'pointer', color: 'var(--on-surface-muted)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '0.8rem', fontWeight: 700, letterSpacing: '0.05em',
              transition: 'background 120ms',
            }}
          >
            ...
          </button>

          {/* Dropdown menu */}
          {menuOpen && (
            <div style={{
              position: 'absolute', top: '110%', right: 0,
              background: 'var(--surface-container)',
              border: '1px solid var(--border)',
              borderRadius: 10, padding: '4px',
              boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
              minWidth: 200, zIndex: 50,
            }}>
              <p style={{ padding: '6px 12px', fontSize: '0.68rem', fontWeight: 700, color: 'var(--on-surface-subtle)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                Move To Project
              </p>
              <button
                type="button"
                onClick={(e) => void handleAssignProject(e, null)}
                disabled={assigning || currentProjectId === null}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  width: '100%', padding: '7px 12px',
                  borderRadius: 7, border: 'none', cursor: assigning || currentProjectId === null ? 'default' : 'pointer',
                  background: 'transparent',
                  color: currentProjectId === null ? 'var(--primary)' : 'var(--on-surface-muted)',
                  fontSize: '0.8125rem', fontWeight: 500, opacity: assigning ? 0.6 : 1,
                }}
              >
                <span>No project</span>
                {currentProjectId === null && <span>✓</span>}
              </button>
              {projects.map((project) => {
                const isSelected = currentProjectId === project.id
                return (
                  <button
                    key={project.id}
                    type="button"
                    onClick={(e) => void handleAssignProject(e, project.id)}
                    disabled={assigning || isSelected}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      width: '100%', padding: '7px 12px',
                      borderRadius: 7, border: 'none', cursor: assigning || isSelected ? 'default' : 'pointer',
                      background: 'transparent',
                      color: isSelected ? 'var(--primary)' : 'var(--on-surface)',
                      fontSize: '0.8125rem', fontWeight: 500, opacity: assigning ? 0.6 : 1,
                    }}
                  >
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{project.name}</span>
                    {isSelected && <span>✓</span>}
                  </button>
                )
              })}

              <div style={{ height: 1, background: 'var(--border)', margin: '4px 2px' }} />
              <button
                type="button"
                onClick={handleDelete}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  width: '100%', padding: '7px 12px',
                  borderRadius: 7, border: 'none', cursor: 'pointer',
                  background: 'transparent', color: 'var(--danger)',
                  fontSize: '0.8125rem', fontWeight: 500,
                  transition: 'background 120ms', opacity: assigning ? 0.6 : 1,
                }}
                disabled={assigning}
                onMouseEnter={e => (e.currentTarget.style.background = 'rgba(248,113,113,0.08)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              >
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
                  <path d="M10 11v6" /><path d="M14 11v6" />
                  <path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2" />
                </svg>
                Delete thread
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/* ─── Project row with 3-dot menu ─── */
function ProjectItem({
  project,
  isExpanded,
  onToggle,
  onRenamed,
  onDeleted,
}: {
  project: ProjectRecord
  isExpanded: boolean
  onToggle: () => void
  onRenamed: (updated: ProjectRecord) => void
  onDeleted: (id: string) => void
}) {
  const [hovered,        setHovered]        = useState(false)
  const [menuOpen,       setMenuOpen]       = useState(false)
  const [renaming,       setRenaming]       = useState(false)
  const [deleting,       setDeleting]       = useState(false)
  const [confirmDelete,  setConfirmDelete]  = useState(false)
  const [nameDraft,      setNameDraft]      = useState('')
  const [nameError,      setNameError]      = useState<string | null>(null)
  const menuRef  = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Close menu on outside click
  useEffect(() => {
    if (!menuOpen) return
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [menuOpen])

  // Focus input when rename mode opens
  useEffect(() => {
    if (!renaming) return
    const t = window.setTimeout(() => inputRef.current?.focus(), 0)
    return () => window.clearTimeout(t)
  }, [renaming])

  const openRename = () => {
    setNameDraft(project.name)
    setNameError(null)
    setMenuOpen(false)
    setRenaming(true)
  }

  const submitRename = async () => {
    const name = nameDraft.trim()
    if (!name) { setNameError('Name is required.'); return }
    if (name === project.name) { setRenaming(false); return }
    setDeleting(true)
    try {
      const updated = await renameProject(project.id, name)
      onRenamed(updated.project)
      setRenaming(false)
    } catch (err) {
      const msg = err instanceof ApiRequestError ? err.message : 'Failed to rename'
      setNameError(msg)
    } finally {
      setDeleting(false)
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    setConfirmDelete(false)
    try {
      await deleteProject(project.id)
      onDeleted(project.id)
    } catch {
      setDeleting(false)
    }
  }

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => { setHovered(false); setMenuOpen(false) }}
    >
      {/* Rename inline input */}
      {renaming ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '2px 4px' }}>
          <input
            ref={inputRef}
            value={nameDraft}
            onChange={(e) => { setNameDraft(e.target.value); setNameError(null) }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') { e.preventDefault(); void submitRename() }
              if (e.key === 'Escape') { e.preventDefault(); setRenaming(false) }
            }}
            style={{
              flex: 1, fontSize: '0.8rem', padding: '4px 8px', borderRadius: 6,
              border: `1px solid ${nameError ? 'var(--danger)' : 'var(--border-accent)'}`,
              background: 'var(--surface-container)', color: 'var(--on-surface)',
              outline: 'none',
            }}
            disabled={deleting}
          />
          <button
            type="button"
            onClick={() => void submitRename()}
            disabled={deleting}
            style={{ fontSize: '0.72rem', padding: '3px 8px', borderRadius: 6, border: 'none', background: 'var(--primary)', color: '#000', fontWeight: 700, cursor: 'pointer' }}
          >
            {deleting ? '…' : 'Save'}
          </button>
          <button
            type="button"
            onClick={() => setRenaming(false)}
            disabled={deleting}
            style={{ fontSize: '0.72rem', padding: '3px 8px', borderRadius: 6, border: '1px solid var(--border)', background: 'transparent', color: 'var(--on-surface-muted)', cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>
      ) : (
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
          {/* Project toggle button */}
          <button
            type="button"
            title={project.name}
            className={`history-item${isExpanded ? ' active' : ''}`}
            onClick={onToggle}
            style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1, paddingRight: 28, opacity: deleting ? 0.4 : 1, pointerEvents: deleting ? 'none' : undefined }}
          >
            <svg
              width="10" height="10" viewBox="0 0 24 24"
              fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
              style={{ flexShrink: 0, transition: 'transform 180ms', transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)', opacity: 0.6 }}
            >
              <polyline points="9 18 15 12 9 6" />
            </svg>
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, textAlign: 'left' }}>
              {project.name}
            </span>
          </button>

          {/* Three-dot button */}
          {(hovered || menuOpen) && !deleting && (
            <div ref={menuRef} style={{ position: 'absolute', right: 4, top: '50%', transform: 'translateY(-50%)', zIndex: 20 }}>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setMenuOpen(v => !v) }}
                title="More options"
                style={{
                  width: 24, height: 24, borderRadius: 6,
                  background: menuOpen ? 'rgba(255,255,255,0.1)' : 'rgba(255,255,255,0.06)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  cursor: 'pointer', color: 'var(--on-surface-muted)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '0.8rem', fontWeight: 700, letterSpacing: '0.05em',
                }}
              >
                ...
              </button>

              {menuOpen && (
                <div style={{
                  position: 'absolute', top: '110%', right: 0,
                  background: 'var(--surface-container)',
                  border: '1px solid var(--border)',
                  borderRadius: 10, padding: 4,
                  boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
                  minWidth: 160, zIndex: 50,
                }}>
                  <button
                    type="button"
                    onClick={openRename}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 8,
                      width: '100%', padding: '7px 12px',
                      borderRadius: 7, border: 'none', cursor: 'pointer',
                      background: 'transparent', color: 'var(--on-surface)',
                      fontSize: '0.8125rem', fontWeight: 500,
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.06)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                      <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
                      <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
                    </svg>
                    Rename
                  </button>
                  <div style={{ height: 1, background: 'var(--border)', margin: '4px 2px' }} />
                  <button
                    type="button"
                    onClick={() => { setMenuOpen(false); setConfirmDelete(true) }}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 8,
                      width: '100%', padding: '7px 12px',
                      borderRadius: 7, border: 'none', cursor: 'pointer',
                      background: 'transparent', color: 'var(--danger)',
                      fontSize: '0.8125rem', fontWeight: 500,
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(248,113,113,0.08)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                      <polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
                      <path d="M10 11v6" /><path d="M14 11v6" />
                      <path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2" />
                    </svg>
                    Delete project
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
      {nameError && <p style={{ fontSize: '0.72rem', color: 'var(--danger)', padding: '2px 8px' }}>{nameError}</p>}

      {/* Custom delete confirmation modal — portalled to body so it's not clipped by sidebar overflow */}
      {confirmDelete && createPortal(
        <div
          style={{
            position: 'fixed', inset: 0, zIndex: 80,
            background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(4px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
          }}
          onClick={() => setConfirmDelete(false)}
        >
          <div
            className="card-elevated"
            style={{ width: '100%', maxWidth: 400, padding: 24 }}
            onClick={(e) => e.stopPropagation()}
          >
            <p style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--on-surface)', marginBottom: 8 }}>
              Delete project?
            </p>
            <p style={{ fontSize: '0.875rem', color: 'var(--on-surface-muted)', marginBottom: 24, lineHeight: 1.5 }}>
              <strong style={{ color: 'var(--on-surface)' }}>{project.name}</strong> will be deleted.
              Threads inside will be unassigned but not deleted.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button
                type="button"
                className="btn btn-ghost btn-pill"
                onClick={() => setConfirmDelete(false)}
                disabled={deleting}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-pill"
                onClick={() => void handleDelete()}
                disabled={deleting}
                style={{ background: 'var(--danger)', color: '#fff', border: 'none' }}
              >
                {deleting ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}

/* ─── Brand ─── */
function Brand() {
  return (
    <div className="brand-wordmark">
      <p className="brand-name" aria-label="Ladder Jobs">
        <span className="brand-name-main">Ladder</span>
        <span className="brand-name-slash">/</span>
        <span className="brand-name-accent">Jobs</span>
      </p>
      <p className="brand-sub">AI Proposal Workflow</p>
    </div>
  )
}

/* ─── Avatar initials ─── */
function Avatar({ name }: { name: string }) {
  const initials = name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase()
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      width: 30, height: 30, borderRadius: '50%',
      background: 'linear-gradient(135deg, var(--primary-glow), rgba(74,222,128,0.25))',
      border: '1px solid var(--border-accent)',
      fontSize: '0.7rem', fontWeight: 700, color: 'var(--primary)',
      flexShrink: 0,
    }}>
      {initials || '?'}
    </span>
  )
}

const SW = 260

export function PhaseLayout() {
  const location = useLocation()
  const navigate  = useNavigate()

  const [open,       setOpen]       = useState(() => window.innerWidth >= 1024)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [isLg,       setIsLg]       = useState(() => window.innerWidth >= 1024)
  const [user,       setUser]       = useState<AuthUser | null>(null)

  const [projects, setProjects] = useState<ProjectRecord[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)
  const [projectModalOpen, setProjectModalOpen] = useState(false)
  const [projectNameDraft, setProjectNameDraft] = useState('')
  const [projectNameError, setProjectNameError] = useState<string | null>(null)
  const [projectCreating, setProjectCreating] = useState(false)
  const projectInputRef = useRef<HTMLInputElement | null>(null)

  const [jobs,    setJobs]    = useState<JobRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [historyRefreshTick, setHistoryRefreshTick] = useState(0)
  const jobsMounted = useRef(true)

  const activeId = useMemo(() => {
    const q = new URLSearchParams(location.search).get('job')
    return q ?? getCurrentJobId() ?? null
  }, [location.search])

  /* Responsive */
  useEffect(() => {
    const mq = window.matchMedia('(min-width: 1024px)')
    const fn = (e: MediaQueryListEvent) => {
      setIsLg(e.matches)
      if (!e.matches) { setOpen(false); setMobileOpen(false) }
    }
    mq.addEventListener('change', fn)
    return () => mq.removeEventListener('change', fn)
  }, [])

  /* Body scroll lock */
  useEffect(() => {
    if (!mobileOpen) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = prev }
  }, [mobileOpen])

  /* Load user */
  useEffect(() => {
    getMe().then((r) => setUser(r.user)).catch(() => null)
  }, [])

  const upsertProject = (project: ProjectRecord) => {
    setProjects((prev) => {
      const existingIndex = prev.findIndex((item) => item.id === project.id)
      if (existingIndex >= 0) {
        const next = [...prev]
        next[existingIndex] = project
        return next
      }
      return [...prev, project]
    })
  }

  const refreshProjects = async () => {
    try {
      const response = await listProjects()
      const nextProjects = response.projects ?? []
      setProjects(nextProjects)
      setSelectedProjectId((currentId) => (
        currentId && !nextProjects.some((project) => project.id === currentId) ? null : currentId
      ))
    } catch {
      // Keep current in-memory list so newly created projects remain visible
      // even if a background refresh temporarily fails.
    }
  }

  useEffect(() => {
    void refreshProjects()
  }, [])

  useEffect(() => {
    if (!projectModalOpen) return
    const timer = window.setTimeout(() => {
      projectInputRef.current?.focus()
    }, 0)
    return () => window.clearTimeout(timer)
  }, [projectModalOpen])

  /* Refresh history when workspace mutates jobs in-place */
  useEffect(() => {
    const onRefresh = () => setHistoryRefreshTick((tick) => tick + 1)
    window.addEventListener(JOBS_HISTORY_REFRESH_EVENT, onRefresh)
    return () => window.removeEventListener(JOBS_HISTORY_REFRESH_EVENT, onRefresh)
  }, [])

  /* Load history — always fetch all jobs; project filtering is done client-side */
  useEffect(() => {
    jobsMounted.current = true
    setLoading(true)
    listJobs({ limit: 80 })
      .then((r) => { if (jobsMounted.current) setJobs(r.jobs ?? []) })
      .catch(() => { if (jobsMounted.current) setJobs([]) })
      .finally(() => { if (jobsMounted.current) setLoading(false) })
    return () => { jobsMounted.current = false }
  }, [location.pathname, location.search, historyRefreshTick])

  const toggle      = () => { if (isLg) setOpen((p) => !p); else setMobileOpen((p) => !p) }
  const closeMobile = () => setMobileOpen(false)
  const newThread   = () => {
    clearCurrentJobId()
    closeMobile()
    if (selectedProjectId) {
      navigate(`/workspace?project=${selectedProjectId}`)
      return
    }
    navigate('/workspace')
  }
  const selectJob   = (id: string) => { setCurrentJobId(id); closeMobile(); navigate(`/workspace?job=${id}`) }
  const deleteThread = (id: string) => {
    setJobs(prev => prev.filter(j => (j.id as string) !== id))
    // If we deleted the currently open thread, go back to blank workspace
    if (activeId === id) { clearCurrentJobId(); navigate('/workspace') }
  }

  const openProjectModal = () => {
    setProjectNameDraft('')
    setProjectNameError(null)
    setProjectModalOpen(true)
  }

  const closeProjectModal = () => {
    if (projectCreating) return
    setProjectModalOpen(false)
    setProjectNameError(null)
  }

  const createProjectFromModal = async () => {
    const name = projectNameDraft.trim()
    if (!name) {
      setProjectNameError('Project name is required.')
      return
    }
    setProjectCreating(true)
    setProjectNameError(null)
    try {
      const created = await createProject(name)
      upsertProject(created.project)
      setSelectedProjectId(created.project.id)
      void refreshProjects()
      setProjectModalOpen(false)
      closeMobile()
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : 'Failed to create project'
      setProjectNameError(message)
    } finally {
      setProjectCreating(false)
    }
  }

  const handleProjectRenamed = (updated: ProjectRecord) => {
    setProjects((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
  }

  const handleProjectDeleted = (id: string) => {
    setProjects((prev) => prev.filter((p) => p.id !== id))
    if (selectedProjectId === id) setSelectedProjectId(null)
    // Unassign threads client-side so "All Threads" updates without refetch
    setJobs((prev) => prev.map((j) => j.project_id === id ? { ...j, project_id: null } : j))
  }

  const assignThreadToProject = async (jobId: string, projectId: string | null) => {
    try {
      await updateJobProject(jobId, { project_id: projectId })
      setHistoryRefreshTick((tick) => tick + 1)
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : 'Failed to move thread to project'
      window.alert(message)
      throw error
    }
  }

  const grouped = useMemo(() => groupJobs(jobs), [jobs])


  /* ─── Sidebar ─── */
  const sidebar = (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-start', padding: '0 12px', height: 56, flexShrink: 0, borderBottom: '1px solid var(--border)' }}>
        <Brand />
      </div>

      {/* New Thread */}
      <div style={{ padding: '12px 10px 10px', flexShrink: 0 }}>
        <button type="button" className="btn btn-primary btn-full btn-pill" onClick={newThread} style={{ height: 38, fontSize: '0.8125rem', fontWeight: 700 }}>
          <IconPlus />
          New Thread
        </button>
      </div>

      {/* Nav */}
      <div style={{ padding: '0 6px', flexShrink: 0 }}>
        <NavLink to="/jobs-dashboard" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
          <IconDashboard />
          Dashboard
        </NavLink>

        <NavLink to="/connectors" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
          <IconLink />
          Connectors
        </NavLink>
        <NavLink to="/usage" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
          <IconChart />
          Usage
        </NavLink>
      </div>

      {/* Divider */}
      <div style={{ margin: '8px 12px', height: 1, background: 'var(--border)', flexShrink: 0 }} />

      {/* Projects + Thread History — combined scrollable area */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '0 6px 8px', minHeight: 0 }}>

        {/* New Project button */}
        <div style={{ padding: '0 4px 6px' }}>
          <button
            type="button"
            className="btn btn-ghost btn-full btn-pill"
            onClick={openProjectModal}
            style={{ height: 34, fontSize: '0.8rem', fontWeight: 700 }}
          >
            <IconPlus />
            New Project
          </button>
        </div>

        {/* Projects label */}
        <div className="section-label" style={{ marginBottom: 6, padding: 0 }}>Projects</div>

        {/* Project list — each expandable */}
        {projects.length === 0 ? (
          <p style={{ fontSize: '0.75rem', color: 'var(--on-surface-muted)', padding: '2px 4px 8px' }}>No projects yet.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginBottom: 4 }}>
            {projects.map((project) => {
              const isExpanded = selectedProjectId === project.id
              return (
                <div key={project.id}>
                  <ProjectItem
                    project={project}
                    isExpanded={isExpanded}
                    onToggle={() => { setSelectedProjectId(isExpanded ? null : project.id); closeMobile() }}
                    onRenamed={handleProjectRenamed}
                    onDeleted={handleProjectDeleted}
                  />

                  {/* Inline threads when expanded — filtered client-side */}
                  {isExpanded && (() => {
                    const projectJobs = jobs.filter((j) => j.project_id === project.id)
                    return (
                      <div style={{
                        marginLeft: 10,
                        paddingLeft: 10,
                        borderLeft: '1px solid var(--border)',
                        marginTop: 2,
                        marginBottom: 4,
                      }}>
                        {loading ? (
                          <p style={{ fontSize: '0.72rem', color: 'var(--on-surface-muted)', padding: '4px 8px' }}>Loading...</p>
                        ) : projectJobs.length === 0 ? (
                          <p style={{ fontSize: '0.72rem', color: 'var(--on-surface-muted)', padding: '4px 8px' }}>No threads in this project yet.</p>
                        ) : (
                          projectJobs.map((job) => (
                            <HistItem
                              key={job.id as string}
                              job={job}
                              isActive={activeId === (job.id as string)}
                              projects={projects}
                              onSelect={selectJob}
                              onDelete={deleteThread}
                              onAssignProject={assignThreadToProject}
                            />
                          ))
                        )}
                      </div>
                    )
                  })()}
                </div>
              )
            })}
          </div>
        )}

        {/* All Threads — always visible */}
        <div style={{ marginTop: 8 }}>
          <div className="section-label" style={{ marginBottom: 6 }}>All Threads</div>
          {loading && <p style={{ fontSize: '0.75rem', color: 'var(--on-surface-muted)', padding: '4px 10px' }}>Loading...</p>}
          {!loading && !jobs.length && (
            <p style={{ fontSize: '0.75rem', color: 'var(--on-surface-muted)', padding: '4px 10px' }}>No threads yet.</p>
          )}
          <HistGroup
            label="Today"
            jobs={grouped.today}
            active={activeId}
            projects={projects}
            onSelect={selectJob}
            onDelete={deleteThread}
            onAssignProject={assignThreadToProject}
          />
          <HistGroup
            label="Yesterday"
            jobs={grouped.yesterday}
            active={activeId}
            projects={projects}
            onSelect={selectJob}
            onDelete={deleteThread}
            onAssignProject={assignThreadToProject}
          />
          <HistGroup
            label="Previous 7 days"
            jobs={grouped.week}
            active={activeId}
            projects={projects}
            onSelect={selectJob}
            onDelete={deleteThread}
            onAssignProject={assignThreadToProject}
          />
          <HistGroup
            label="Older"
            jobs={grouped.older}
            active={activeId}
            projects={projects}
            onSelect={selectJob}
            onDelete={deleteThread}
            onAssignProject={assignThreadToProject}
          />
        </div>
      </div>

      {/* ─── Profile footer ─── */}
      <div style={{ flexShrink: 0, borderTop: '1px solid var(--border)' }}>
        <NavLink
          to="/profile"
          className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
          style={{ margin: '6px 6px 6px', padding: '8px 10px', display: 'flex', alignItems: 'center', gap: 9, borderRadius: 9 }}
        >
          <Avatar name={user?.display_name ?? '?'} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <p style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--on-surface)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user?.display_name ?? 'Profile'}
            </p>
            <p style={{ fontSize: '0.68rem', color: 'var(--on-surface-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user?.email ?? ''}
            </p>
          </div>
        </NavLink>
      </div>
    </div>
  )

  return (
    <div className="app-bg" style={{ display: 'flex', height: '100svh', overflow: 'hidden', color: 'var(--on-surface)' }}>

      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div onClick={closeMobile} style={{ position: 'fixed', inset: 0, zIndex: 40, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }} />
      )}

      {/* Sidebar */}
      <aside style={{
        width: SW, flexShrink: 0,
        background: 'var(--surface-low)',
        borderRight: '1px solid var(--border)',
        transition: 'transform 280ms cubic-bezier(0.4,0,0.2,1), margin 280ms cubic-bezier(0.4,0,0.2,1)',
        ...(isLg ? {
          position: 'relative',
          transform: open ? 'translateX(0)' : `translateX(-${SW}px)`,
          marginRight: open ? 0 : -SW,
          zIndex: 1,
        } : {
          position: 'fixed',
          top: 0, left: 0, bottom: 0,
          zIndex: 50,
          transform: mobileOpen ? 'translateX(0)' : `translateX(-${SW}px)`,
          boxShadow: mobileOpen ? '4px 0 32px rgba(0,0,0,0.5)' : 'none',
        }),
      }}>
        {sidebar}
      </aside>

      {/* Main */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
        <header style={{
          display: 'flex', alignItems: 'center', gap: 10,
          height: 56, padding: '0 20px',
          borderBottom: '1px solid var(--border)',
          flexShrink: 0,
          background: 'rgba(10,12,11,0.8)',
          backdropFilter: 'blur(12px)',
        }}>
          <button className="icon-btn" onClick={toggle} aria-label="Toggle sidebar">
            <IconMenu />
          </button>
          {isLg && !open && <Brand />}
        </header>

        <div style={{ flex: 1, overflowY: 'auto', padding: '28px 28px 48px' }}>
          <Outlet />
        </div>
      </main>

      {projectModalOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 80,
            background: 'rgba(0,0,0,0.55)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 16,
          }}
          onClick={closeProjectModal}
        >
          <div
            className="card-elevated"
            style={{ width: '100%', maxWidth: 440, padding: 18 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <p style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--on-surface)' }}>New Project</p>
              <button type="button" className="icon-btn" onClick={closeProjectModal} aria-label="Close create project modal">
                x
              </button>
            </div>

            <label htmlFor="new-project-name" className="section-label" style={{ marginBottom: 8, display: 'block', padding: 0 }}>
              Project Name
            </label>
            <input
              id="new-project-name"
              ref={projectInputRef}
              className="input"
              value={projectNameDraft}
              onChange={(e) => {
                setProjectNameDraft(e.target.value)
                if (projectNameError) setProjectNameError(null)
              }}
              placeholder="e.g. AI, Web, Automation"
              maxLength={120}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  void createProjectFromModal()
                }
                if (e.key === 'Escape') {
                  e.preventDefault()
                  closeProjectModal()
                }
              }}
            />

            {projectNameError && (
              <p style={{ marginTop: 8, fontSize: '0.8rem', color: 'var(--danger)' }}>{projectNameError}</p>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
              <button type="button" className="btn btn-ghost btn-pill" onClick={closeProjectModal} disabled={projectCreating}>
                Cancel
              </button>
              <button type="button" className="btn btn-primary btn-pill" onClick={() => void createProjectFromModal()} disabled={projectCreating}>
                {projectCreating ? 'Creating...' : 'Create Project'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}


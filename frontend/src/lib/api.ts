export type ApiErrorPayload = {
  error?: {
    code?: string
    message?: string
    detail?: unknown
  }
  detail?: unknown
}

export class ApiRequestError extends Error {
  status: number
  payload: ApiErrorPayload | null

  constructor(message: string, status: number, payload: ApiErrorPayload | null) {
    super(message)
    this.name = 'ApiRequestError'
    this.status = status
    this.payload = payload
  }
}

type RequestOptions = Omit<RequestInit, 'body'> & {
  body?: unknown
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, headers, ...rest } = options
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(headers ?? {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (response.status === 204) {
    return undefined as T
  }

  let payload: ApiErrorPayload | null = null
  try {
    payload = (await response.json()) as ApiErrorPayload
  } catch {
    payload = null
  }

  if (response.status === 401) {
    const isAuthMutation = path === '/api/v1/auth/login' || path === '/api/v1/auth/register'
    if (!isAuthMutation) {
      window.localStorage.removeItem('ladderjobs.hasSession')
      window.localStorage.removeItem('ladderjobs.hasProfile')
      if (window.location.pathname !== '/auth') {
        window.location.href = '/auth'
      }
      throw new ApiRequestError('Session expired. Please log in again.', 401, payload)
    }
    // Login/register 401 = wrong credentials — fall through to generic error handler
  }

  if (!response.ok) {
    const message =
      payload?.error?.message ||
      (typeof payload?.detail === 'string' ? payload.detail : null) ||
      `Request failed with status ${response.status}`
    throw new ApiRequestError(message, response.status, payload)
  }

  return payload as T
}

export type AuthUser = {
  id: string
  display_name: string
  email: string
}

export type AuthResponse = {
  user: AuthUser
}

export type RegisterPayload = {
  display_name: string
  email: string
  password: string
}

export type LoginPayload = {
  email: string
  password: string
}

export type PromptBlock = {
  title: string
  content: string
  enabled: boolean
}

export type UserProfile = {
  id: string
  user_id: string
  upwork_profile_url: string | null
  upwork_profile_id: string | null
  upwork_profile_markdown: string | null
  proposal_template: string | null
  doc_template: string | null
  loom_template: string | null
  workflow_template_notes: string | null
  custom_global_instruction: string | null
  custom_prompt_blocks: PromptBlock[]
}

export type ProfilePayload = {
  upwork_profile_url?: string | null
  upwork_profile_id?: string | null
  upwork_profile_markdown?: string | null
  proposal_template?: string | null
  doc_template?: string | null
  loom_template?: string | null
  workflow_template_notes?: string | null
  custom_global_instruction?: string | null
  custom_prompt_blocks?: PromptBlock[]
}

export type ConnectorRecord = {
  id: string
  user_id: string
  connector_name: string
  credential_ref: string
  status: string
  updated_at: string
}

export type ConnectorStatus = {
  connector_name: string
  status: string
  is_connected: boolean
  action_required: boolean
  message: string
  checked_live?: boolean
  details?: Record<string, unknown>
}

export type JobOutcome = 'sent' | 'not_sent' | 'hired'

export type JobIntakePayload = {
  job_url: string
  notes_markdown?: string
  project_id?: string | null
}

export type JobRecord = {
  id?: string
  user_id?: string
  project_id?: string | null
  job_url?: string
  upwork_job_id?: string | null
  notes_markdown?: string | null
  job_markdown?: string | null
  job_explanation?: string | null
  extraction_error?: string | null
  requires_manual_markdown?: boolean
  status?: string
  plan_approved?: boolean
  is_submitted_to_upwork?: boolean
  submitted_at?: string | null
  outcome?: JobOutcome | null
  job_type?: string | null
  automation_platform?: string | null
  classification_confidence?: string | null
  classification_reasoning?: string | null
  classified_at?: string | null
  created_at?: string | null
  updated_at?: string | null
  duplicate_decision?: string | null
  duplicate_count?: number
  [key: string]: unknown
}

export type GenerationRun = {
  id?: string
  status?: string
  run_type?: string
  artifact_type?: string | null
  target_artifact?: string | null
  input_tokens?: number | null
  output_tokens?: number | null
  estimated_cost_usd?: number | null
  latency_ms?: number | null
  failure_message?: string | null
  failure_reason?: string | null
  created_at?: string | null
  completed_at?: string | null
  [key: string]: unknown
}

export type WorkflowJsonItem = {
  name: string
  workflow_json: Record<string, unknown>
}

export type JobOutput = {
  id: string
  job_id: string
  google_doc_url: string | null
  google_doc_markdown: string | null
  workflow_jsons: WorkflowJsonItem[]
  loom_script: string | null
  proposal_text: string | null
  extra_files_json: Array<Record<string, unknown>>
  edit_log_json: Array<Record<string, unknown>>
  artifact_versions_json: Array<Record<string, unknown>>
  approval_snapshot_json: Record<string, unknown> | null
  ai_usage_summary_json: Record<string, unknown> | null
  doc_flowchart: {
    status?: string
    image_url?: string | null
    inline_svg_data_url?: string | null
    error?: string | null
    words_sent?: number
    estimated_credits_used?: number
    estimated_free_weekly_images_at_this_size?: number
    flowchart_instruction?: string | null
    request_id?: string | null
    render_engine?: string | null
    render_mode?: 'ai' | 'fallback' | string | null
    layout_family?: string | null
    orientation?: 'horizontal' | string | null
    creativity_level?: 'low' | 'medium' | 'high' | string | null
    connection_style?: 'clean' | 'orthogonal' | 'curved' | string | null
    model_name?: string | null
    provider_name?: string | null
    spec_source?: string | null
    input_tokens?: number | null
    output_tokens?: number | null
    quality_score?: number | null
    quality_status?: string | null
    validation_errors?: string[]
    validation_warnings?: string[]
    validation_attempts?: Array<Record<string, unknown>>
  } | null
  updated_at: string | null
}

export type JobIntakeResponse = {
  job: JobRecord
  duplicate: {
    duplicate_count: number
    user_ids: string[]
    job_ids: string[]
    display_names?: string[]
  }
}

export type JobDetailResponse = {
  job: JobRecord
  output: JobOutput | null
  duplicates?: string[]
}

export type DuplicateDecisionResponse = {
  job: JobRecord
  should_process: boolean
}

export type JobExtractionResponse = {
  job: JobRecord
  queued: boolean
  extracted: boolean
  fallback_required: boolean
  message: string
}

export type JobGenerateResponse = {
  queued: boolean
  run: GenerationRun | null
  message: string
}

export type GenerationRunsResponse = {
  runs: GenerationRun[]
  count: number
}

export type JobListResponse = {
  jobs: JobRecord[]
  count: number
}

export type ProjectRecord = {
  id: string
  user_id: string
  name: string
  created_at: string | null
  updated_at: string | null
}

export type ProjectListResponse = {
  projects: ProjectRecord[]
  count: number
}

export type JobOutputResponse = {
  output: JobOutput
}

export type JobApproveResponse = {
  job: JobRecord
  output: JobOutput
  message: string
}

export type PublishResult = {
  connector_name: string
  status: string
  external_id?: string | null
  external_url?: string | null
  message?: string | null
  metadata?: {
    diagram_included?: boolean;
    diagram_reason?: string;
    flowchart_section_removed?: boolean;
    [key: string]: unknown;
  } | null
  reason?: string | null
}

export type JobPublishResponse = {
  job_id: string
  published_at: string
  results: PublishResult[]
  google_doc_url: string | null
  google_doc_open_url?: string | null
}

export type OutputRegenerateResponse = {
  queued: boolean
  run: GenerationRun | null
  output: JobOutput | null
  regenerated_output: string
  message: string
}

export type DocFlowchartGenerateResponse = {
  output: JobOutput
  doc_flowchart: JobOutput['doc_flowchart'] | null
  message: string
}

export function register(payload: RegisterPayload) {
  return requestJson<AuthResponse>('/api/v1/auth/register', {
    method: 'POST',
    body: payload,
  })
}

export function login(payload: LoginPayload) {
  return requestJson<AuthResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: payload,
  })
}

export function getMe() {
  return requestJson<AuthResponse>('/api/v1/auth/me')
}

export function updateDisplayName(display_name: string) {
  return requestJson<AuthResponse>('/api/v1/auth/me', {
    method: 'PATCH',
    body: JSON.stringify({ display_name }),
  })
}

export function logout() {
  return requestJson<void>('/api/v1/auth/logout', { method: 'POST' })
}

export function getProfile() {
  return requestJson<UserProfile>('/api/v1/profile')
}

export function createProfile(payload: ProfilePayload) {
  return requestJson<UserProfile>('/api/v1/profile', {
    method: 'POST',
    body: payload,
  })
}

export function updateProfile(payload: ProfilePayload) {
  return requestJson<UserProfile>('/api/v1/profile', {
    method: 'PATCH',
    body: payload,
  })
}

export type UsageTotalsResponse = {
  runs_total: number
  runs_success: number
  runs_failed: number
  input_tokens_total: number
  output_tokens_total: number
  estimated_cost_usd_total: number
  last_activity_at: string | null
}

export type UsageUserResponse = {
  user_id: string
  display_name: string
  email: string
  totals: UsageTotalsResponse
}

export type UsageSummaryResponse = {
  generated_at: string
  window_days: number | null
  window_start_at: string | null
  window_end_at: string
  current_user: UsageUserResponse
  team_totals: UsageTotalsResponse
  team_users: UsageUserResponse[]
  team_user_count: number
  active_user_count: number
}

export function getUsageSummary(windowDays?: number) {
  const q = windowDays ? `?window_days=${windowDays}` : ''
  return requestJson<UsageSummaryResponse>(`/api/v1/usage/summary${q}`)
}

export type JobsDashboardWindow = 'day' | 'week' | 'month'

export type JobsDashboardUserStatsResponse = {
  rank: number | null
  user_id: string
  display_name: string
  email: string
  proposals_sent_in_window: number
  avg_send_speed_per_day: number
  total_jobs_sent_all_time: number
  total_ai_cost_usd_all_time: number
}

export type JobsDashboardResponse = {
  generated_at: string
  window_key: JobsDashboardWindow
  window_days: number
  window_start_at: string
  window_end_at: string
  current_user: JobsDashboardUserStatsResponse
  leaderboard: JobsDashboardUserStatsResponse[]
  leaderboard_user_count: number
}

export function getJobsDashboard(window: JobsDashboardWindow = 'week') {
  return requestJson<JobsDashboardResponse>(`/api/v1/dashboard/jobs?window=${window}`)
}

export type UpworkExtractResponse = {
  profile: UserProfile
  extracted: boolean
  message: string
}

/** POST — create profile if missing, extract markdown from Upwork URL */
export function extractUpworkProfile(upworkProfileUrl: string) {
  return requestJson<UpworkExtractResponse>('/api/v1/profile/extract-upwork', {
    method: 'POST',
    body: { upwork_profile_url: upworkProfileUrl },
  })
}

/** PATCH — re-extract from existing or new URL into existing profile */
export function refreshUpworkProfile(upworkProfileUrl?: string) {
  return requestJson<UpworkExtractResponse>('/api/v1/profile/extract-upwork', {
    method: 'PATCH',
    body: { upwork_profile_url: upworkProfileUrl ?? null },
  })
}

export type BeautifyManualResponse = {
  profile: UserProfile
  beautified_markdown: string
  model_name: string
  input_tokens: number
  output_tokens: number
  message: string
}

/** POST — beautify raw/unstructured profile text via AI into clean markdown */
export function beautifyManualProfile(rawProfileText: string) {
  return requestJson<BeautifyManualResponse>('/api/v1/profile/beautify-manual', {
    method: 'POST',
    body: { raw_profile_text: rawProfileText },
  })
}

export function listConnectors() {
  return requestJson<{ connectors: ConnectorRecord[] }>('/api/v1/connectors')
}

export function createConnector(payload: {
  connector_name: string
  credential_ref: string
  status: string
}) {
  return requestJson<{ connector: ConnectorRecord }>('/api/v1/connectors', {
    method: 'POST',
    body: payload,
  })
}

export function updateConnector(
  connectorName: string,
  payload: {
    credential_ref?: string
    status?: string
  },
) {
  return requestJson<{ connector: ConnectorRecord }>(`/api/v1/connectors/${connectorName}`, {
    method: 'PATCH',
    body: payload,
  })
}

export function deleteConnector(connectorName: string) {
  return requestJson<void>(`/api/v1/connectors/${connectorName}`, {
    method: 'DELETE',
  })
}

export type GoogleOAuthStartResponse = {
  authorization_url: string
  state: string
  redirect_uri: string
  expires_in_seconds: number
}

export function startGoogleOAuth() {
  return requestJson<GoogleOAuthStartResponse>('/api/v1/connectors/google/oauth/start')
}


export function getConnectorStatus(connectorName: string, options?: { live?: boolean }) {
  const search = new URLSearchParams()
  if (options?.live) search.set('live', 'true')
  const query = search.toString()
  return requestJson<{ connector_status: ConnectorStatus }>(
    `/api/v1/connectors/${connectorName}/status${query ? `?${query}` : ''}`,
  )
}

export function createJobIntake(payload: JobIntakePayload) {
  return requestJson<JobIntakeResponse>('/api/v1/jobs/intake', {
    method: 'POST',
    body: payload,
  })
}

export function listJobs(params?: {
  limit?: number
  offset?: number
  status?: string
  outcome?: JobOutcome
  project_id?: string
  is_submitted_to_upwork?: boolean
}) {
  const search = new URLSearchParams()
  if (params?.limit !== undefined) search.set('limit', String(params.limit))
  if (params?.offset !== undefined) search.set('offset', String(params.offset))
  if (params?.status) search.set('status', params.status)
  if (params?.outcome) search.set('outcome', params.outcome)
  if (params?.project_id) search.set('project_id', params.project_id)
  if (params?.is_submitted_to_upwork !== undefined) {
    search.set('is_submitted_to_upwork', String(params.is_submitted_to_upwork))
  }
  const query = search.toString()
  return requestJson<JobListResponse>(`/api/v1/jobs${query ? `?${query}` : ''}`)
}

export function getJobDetail(jobId: string) {
  return requestJson<JobDetailResponse>(`/api/v1/jobs/${jobId}`)
}

export function deleteJob(jobId: string) {
  return requestJson<void>(`/api/v1/jobs/${jobId}`, { method: 'DELETE' })
}

export function sendDuplicateDecision(jobId: string, action: 'continue' | 'stop') {
  return requestJson<DuplicateDecisionResponse>(`/api/v1/jobs/${jobId}/duplicate-decision`, {
    method: 'POST',
    body: { action },
  })
}

export function extractJob(jobId: string) {
  return requestJson<JobExtractionResponse>(`/api/v1/jobs/${jobId}/extract`, {
    method: 'POST',
  })
}

export type JobExplainResponse = {
  job: JobRecord
  used_fallback: boolean
  message: string
}

export function explainJob(jobId: string) {
  return requestJson<JobExplainResponse>(`/api/v1/jobs/${jobId}/explain`, {
    method: 'POST',
  })
}

export function saveManualMarkdown(jobId: string, jobMarkdown: string) {
  return requestJson<JobExtractionResponse>(`/api/v1/jobs/${jobId}/manual-markdown`, {
    method: 'POST',
    body: { job_markdown: jobMarkdown },
  })
}

export function updateJobStatusOutcome(
  jobId: string,
  payload: { status?: string | null; outcome?: JobOutcome | null },
) {
  return requestJson<JobDetailResponse>(`/api/v1/jobs/${jobId}/status-outcome`, {
    method: 'PATCH',
    body: payload,
  })
}

export function updateJobSubmission(
  jobId: string,
  payload: { is_submitted_to_upwork: boolean; submitted_at?: string | null },
) {
  return requestJson<JobDetailResponse>(`/api/v1/jobs/${jobId}/submission`, {
    method: 'PATCH',
    body: payload,
  })
}

export function updateJobProject(
  jobId: string,
  payload: { project_id?: string | null },
) {
  return requestJson<JobDetailResponse>(`/api/v1/jobs/${jobId}/project`, {
    method: 'PATCH',
    body: payload,
  })
}

export function listProjects() {
  return requestJson<ProjectListResponse>('/api/v1/projects')
}

export function createProject(name: string) {
  return requestJson<{ project: ProjectRecord }>('/api/v1/projects', {
    method: 'POST',
    body: { name },
  })
}

export function renameProject(projectId: string, name: string) {
  return requestJson<{ project: ProjectRecord }>(`/api/v1/projects/${projectId}`, {
    method: 'PATCH',
    body: { name },
  })
}

export function deleteProject(projectId: string) {
  return requestJson<void>(`/api/v1/projects/${projectId}`, {
    method: 'DELETE',
  })
}

export function generateJob(
  jobId: string,
  payload?: { instruction?: string; queue_if_available?: boolean },
) {
  return requestJson<JobGenerateResponse>(`/api/v1/jobs/${jobId}/generate`, {
    method: 'POST',
    body: {
      instruction: payload?.instruction,
      queue_if_available: payload?.queue_if_available ?? true,
    },
  })
}

export function listGenerationRuns(jobId: string) {
  return requestJson<GenerationRunsResponse>(`/api/v1/jobs/${jobId}/generation-runs`)
}

export function getJobOutputs(jobId: string) {
  return requestJson<JobOutputResponse>(`/api/v1/jobs/${jobId}/outputs`)
}

export function updateJobOutputs(
  jobId: string,
  payload: {
    google_doc_url?: string | null
    google_doc_markdown?: string | null
    workflow_jsons?: WorkflowJsonItem[] | null
    loom_script?: string | null
    proposal_text?: string | null
  },
) {
  return requestJson<JobOutputResponse>(`/api/v1/jobs/${jobId}/outputs`, {
    method: 'PATCH',
    body: payload,
  })
}

export function regenerateOutput(
  jobId: string,
  outputType: 'proposal' | 'loom_script' | 'workflow' | 'doc',
  payload?: { instruction?: string; queue_if_available?: boolean },
) {
  return requestJson<OutputRegenerateResponse>(`/api/v1/jobs/${jobId}/outputs/${outputType}/regenerate`, {
    method: 'POST',
    body: {
      instruction: payload?.instruction,
      queue_if_available: payload?.queue_if_available ?? true,
    },
  })
}

export function generateDocFlowchart(
  jobId: string,
  payload?: { instruction?: string; connection_style?: 'clean' | 'orthogonal' | 'curved' }
) {
  return requestJson<DocFlowchartGenerateResponse>(`/api/v1/jobs/${jobId}/outputs/doc-flowchart/generate`, {
    method: 'POST',
    body: {
      instruction: payload?.instruction,
      connection_style: payload?.connection_style,
    },
  })
}

export function approveJob(jobId: string, notes?: string) {
  return requestJson<JobApproveResponse>(`/api/v1/jobs/${jobId}/approve`, {
    method: 'POST',
    body: { notes },
  })
}

export function publishJob(
  jobId: string,
  payload?: {
    connectors?: string[]
    title?: string
  },
) {
  return requestJson<JobPublishResponse>(`/api/v1/jobs/${jobId}/publish`, {
    method: 'POST',
    body: payload ?? {},
  })
}

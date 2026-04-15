export type ScreenStatus = 'ready' | 'upcoming'

export type ScreenDefinition = {
  id: number
  slug: string
  title: string
  folder: string
  status: ScreenStatus
}

export const screens: ScreenDefinition[] = [
  {
    id: 1,
    slug: 'authentication-login-register',
    title: 'Sign In / Register',
    folder: 'authentication_login_register',
    status: 'ready',
  },
  {
    id: 2,
    slug: 'job-intake-workspace',
    title: 'Job Intake Workspace',
    folder: 'job_intake_workspace',
    status: 'ready',
  },
  {
    id: 3,
    slug: 'clarification-plan-confirmation',
    title: 'Clarification & Plan',
    folder: 'clarification_plan_confirmation',
    status: 'ready',
  },
  {
    id: 4,
    slug: 'connector-management-1',
    title: 'Connector Management A',
    folder: 'connector_management_1',
    status: 'upcoming',
  },
  {
    id: 5,
    slug: 'connector-management-2',
    title: 'Connector Management B',
    folder: 'connector_management_2',
    status: 'upcoming',
  },
  {
    id: 6,
    slug: 'generation-progress',
    title: 'Generation Progress',
    folder: 'generation_progress',
    status: 'upcoming',
  },
  {
    id: 7,
    slug: 'output-dashboard',
    title: 'Output Dashboard',
    folder: 'output_dashboard',
    status: 'upcoming',
  },
  {
    id: 8,
    slug: 'duplicate-decision',
    title: 'Duplicate Decision',
    folder: 'duplicate_decision',
    status: 'upcoming',
  },
  {
    id: 9,
    slug: 'targeted-regeneration',
    title: 'Targeted Regeneration',
    folder: 'targeted_regeneration',
    status: 'upcoming',
  },
  {
    id: 10,
    slug: 'extraction-manual-fallback-1',
    title: 'Manual Fallback A',
    folder: 'extraction_manual_fallback_1',
    status: 'upcoming',
  },
  {
    id: 11,
    slug: 'extraction-manual-fallback-2',
    title: 'Manual Fallback B',
    folder: 'extraction_manual_fallback_2',
    status: 'upcoming',
  },
  {
    id: 12,
    slug: 'publish-outputs',
    title: 'Publish Outputs',
    folder: 'publish_outputs',
    status: 'upcoming',
  },
  {
    id: 13,
    slug: 'history-list',
    title: 'History List',
    folder: 'history_list',
    status: 'upcoming',
  },
  {
    id: 14,
    slug: 'history-detail',
    title: 'History Detail',
    folder: 'history_detail',
    status: 'upcoming',
  },
  {
    id: 15,
    slug: 'profile-preferences',
    title: 'Profile Preferences',
    folder: 'profile_preferences',
    status: 'upcoming',
  },
]

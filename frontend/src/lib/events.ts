export const JOBS_HISTORY_REFRESH_EVENT = 'ladder:jobs-history-refresh'

export function notifyJobsHistoryRefresh() {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new Event(JOBS_HISTORY_REFRESH_EVENT))
}

const CURRENT_JOB_ID_KEY = 'ladderjobs.currentJobId'

export function setCurrentJobId(jobId: string) {
  window.localStorage.setItem(CURRENT_JOB_ID_KEY, jobId)
}

export function getCurrentJobId() {
  return window.localStorage.getItem(CURRENT_JOB_ID_KEY)
}

export function clearCurrentJobId() {
  window.localStorage.removeItem(CURRENT_JOB_ID_KEY)
}

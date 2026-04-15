const SESSION_HINT_KEY = 'ladderjobs.hasSession'
const PROFILE_HINT_KEY = 'ladderjobs.hasProfile'

export function hasSessionHint() {
  return window.localStorage.getItem(SESSION_HINT_KEY) === '1'
}

export function markSessionHint() {
  window.localStorage.setItem(SESSION_HINT_KEY, '1')
}

export function clearSessionHint() {
  window.localStorage.removeItem(SESSION_HINT_KEY)
  window.localStorage.removeItem(PROFILE_HINT_KEY)
}

export function hasProfileHint() {
  return window.localStorage.getItem(PROFILE_HINT_KEY) === '1'
}

export function markProfileHint() {
  window.localStorage.setItem(PROFILE_HINT_KEY, '1')
}

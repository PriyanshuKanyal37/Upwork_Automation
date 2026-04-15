import { useEffect, useState } from 'react'
import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { PhaseLayout } from './components/PhaseLayout'
import { getProfile } from './lib/api'
import { hasProfileHint, hasSessionHint, markProfileHint } from './lib/session'
import { AuthenticationPage } from './pages/AuthenticationPage'
import { ConnectorsPage } from './pages/ConnectorsPage'
import { OnboardingPage } from './pages/OnboardingPage'
import { ProfilePage } from './pages/ProfilePage'
import { JobsDashboardPage } from './pages/JobsDashboardPage'
import { WorkspacePage } from './pages/WorkspacePage'
import { UsagePage } from './pages/UsagePage'

function ProtectedRoutes() {
  if (!hasSessionHint()) {
    return <Navigate to="/auth" replace />
  }

  return <Outlet />
}

/** 
 * ProfileGuard checks if the user has a profile. 
 * If not, and they're not on /onboarding, it redirects to /onboarding.
 * If they HAVE a profile and are on /onboarding, it redirects to /workspace.
 */
function ProfileGuard() {
  const location = useLocation()
  const [loading, setLoading] = useState(!hasProfileHint()) // No hint? Must check API.
  const [hasProfile, setHasProfile] = useState(hasProfileHint())
  
  const isOnboarding = location.pathname === '/onboarding'

  useEffect(() => {
    let cancelled = false

    if (hasProfileHint()) {
      setHasProfile(true)
      setLoading(false)
      return () => {
        cancelled = true
      }
    }

    setLoading(true)
    void (async () => {
      try {
        const p = await getProfile()
        if (!cancelled && p) {
          markProfileHint()
          setHasProfile(true)
        }
      } catch {
        if (!cancelled) {
          setHasProfile(false)
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    })()

    return () => {
      cancelled = true
    }
  }, [location.pathname])

  if (loading) {
    return (
      <div className="app-bg" style={{ height: '100svh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <p className="page-eyebrow" style={{ animation: 'pulse 1.5s infinite' }}>Verifying Identity...</p>
      </div>
    )
  }

  // Mandatory onboarding check
  if (!hasProfile && !isOnboarding) {
    return <Navigate to="/onboarding" replace />
  }

  // Already onboarded? Don't allow going back to onboarding
  if (hasProfile && isOnboarding) {
    return <Navigate to="/workspace" replace />
  }

  return <Outlet />
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/auth" replace />} />
      <Route path="/auth" element={<AuthenticationPage />} />
      <Route
        path="/phase/authentication-login-register"
        element={<Navigate to="/auth" replace />}
      />
      <Route
        path="/phase/job-intake-workspace"
        element={<Navigate to="/workspace" replace />}
      />
      <Route
        path="/phase/clarification-plan-confirmation"
        element={<Navigate to="/workspace" replace />}
      />
      
      <Route element={<ProtectedRoutes />}>
        <Route element={<ProfileGuard />}>
          <Route path="/onboarding" element={<OnboardingPage />} />
          
          <Route element={<PhaseLayout />}>
            <Route path="/workspace" element={<WorkspacePage />} />
            <Route path="/jobs-dashboard" element={<JobsDashboardPage />} />
            <Route path="/connectors" element={<ConnectorsPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/usage" element={<UsagePage />} />
            <Route path="/intake" element={<Navigate to="/workspace" replace />} />
            <Route path="/clarification" element={<Navigate to="/workspace" replace />} />
          </Route>
        </Route>
      </Route>
      
      <Route path="*" element={<Navigate to="/auth" replace />} />
    </Routes>
  )
}

export default App



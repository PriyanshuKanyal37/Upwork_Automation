import { useEffect, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { getJobsDashboard, type JobsDashboardResponse, type JobsDashboardWindow } from '../lib/api'
import { clearCurrentJobId } from '../lib/currentJob'

const fNum = (n: number) => new Intl.NumberFormat('en-US').format(n)
const fUsd = (n: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n)

const StatCard = ({ label, value, sub }: { label: string; value: ReactNode; sub?: string }) => (
  <div className="card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 8 }}>
    <div
      style={{
        fontSize: '0.8125rem',
        fontWeight: 600,
        color: 'var(--on-surface-muted)',
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
      }}
    >
      {label}
    </div>
    <div style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--on-surface)' }}>{value}</div>
    {sub && <div style={{ fontSize: '0.75rem', color: 'var(--on-surface-subtle)' }}>{sub}</div>}
  </div>
)

export function JobsDashboardPage() {
  const navigate = useNavigate()
  const [windowKey, setWindowKey] = useState<JobsDashboardWindow>('day')
  const [data, setData] = useState<JobsDashboardResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    setLoading(true)
    getJobsDashboard(windowKey)
      .then((res) => {
        if (active) {
          setData(res)
          setLoading(false)
        }
      })
      .catch((err) => {
        console.error(err)
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [windowKey])

  return (
    <div className="page-container" style={{ padding: '32px 40px', overflowY: 'auto', height: '100%' }}>
      <div style={{ maxWidth: 980, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 28 }}>

        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--on-surface-muted)' }}>Loading dashboard...</div>
        ) : !data ? (
          <div className="card" style={{ padding: '40px', textAlign: 'center', color: 'var(--danger)' }}>
            Failed to load dashboard data.
          </div>
        ) : (
          <>
            <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16 }}>
              <button
                className="card"
                onClick={() => {
                  clearCurrentJobId()
                  navigate('/workspace')
                }}
                style={{
                  padding: '20px', display: 'flex', flexDirection: 'column', gap: 8,
                  alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
                  background: 'linear-gradient(135deg, rgba(74,222,128,0.1), rgba(74,222,128,0.02))',
                  border: '1px dashed var(--primary)', transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                  height: '100%', minHeight: 120,
                  boxShadow: 'inset 0 1px 4px rgba(255,255,255,0.05)',
                }}
                onMouseEnter={e => e.currentTarget.style.background = 'rgba(74,222,128,0.15)'}
                onMouseLeave={e => e.currentTarget.style.background = 'linear-gradient(135deg, rgba(74,222,128,0.1), rgba(74,222,128,0.02))'}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 36, height: 36, borderRadius: '50%', background: 'rgba(74,222,128,0.15)', color: 'var(--primary)', marginBottom: 4 }}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <line x1="12" y1="5" x2="12" y2="19" />
                    <line x1="5" y1="12" x2="19" y2="12" />
                  </svg>
                </div>
                <div style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--primary)' }}>New Thread</div>
              </button>

              <StatCard
                label="Total Jobs Sent"
                value={fNum(data.current_user.total_jobs_sent_all_time)}
                sub="All-time"
              />
              <StatCard
                label="Total AI Cost"
                value={fUsd(data.current_user.total_ai_cost_usd_all_time)}
                sub="All-time estimated"
              />
              <StatCard
                label="Average Send Speed"
                value={`${data.current_user.avg_send_speed_per_day.toFixed(2)}/day`}
                sub="Window average"
              />
            </section>

            <section style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h2 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--on-surface)' }}>
                  Jobs Leaderboard
                </h2>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--on-surface-muted)' }}>Window:</span>
                  <select
                    className="input btn-pill"
                    style={{ width: 'auto', paddingRight: 36, height: 32, fontSize: '0.8125rem', paddingLeft: 14, minHeight: 32 }}
                    value={windowKey}
                    onChange={(e) => setWindowKey(e.target.value as JobsDashboardWindow)}
                  >
                    <option value="day">Daily</option>
                    <option value="week">Weekly</option>
                    <option value="month">Monthly</option>
                  </select>
                </div>
              </div>
              <div className="card" style={{ overflow: 'hidden' }}>
                <div style={{ overflowX: 'auto' }}>
                  <table
                    style={{
                      width: '100%',
                      minWidth: 700,
                      borderCollapse: 'collapse',
                      textAlign: 'left',
                      fontSize: '0.875rem',
                    }}
                  >
                    <thead>
                      <tr style={{ background: 'rgba(255,255,255,0.02)', borderBottom: '1px solid var(--border)' }}>
                        <th style={{ padding: '14px 16px', color: 'var(--on-surface-muted)', fontWeight: 600 }}>Rank</th>
                        <th style={{ padding: '14px 16px', color: 'var(--on-surface-muted)', fontWeight: 600 }}>User</th>
                        <th style={{ padding: '14px 16px', color: 'var(--on-surface-muted)', fontWeight: 600 }}>Sent (Window)</th>
                        <th style={{ padding: '14px 16px', color: 'var(--on-surface-muted)', fontWeight: 600 }}>Avg Speed</th>
                        <th style={{ padding: '14px 16px', color: 'var(--on-surface-muted)', fontWeight: 600 }}>Total Sent</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.leaderboard.map((item, index) => (
                        <tr key={item.user_id} style={{ borderBottom: index < data.leaderboard.length - 1 ? '1px solid var(--border)' : 'none' }}>
                          <td style={{ padding: '14px 16px', fontWeight: 700, color: 'var(--primary)' }}>{item.rank}</td>
                          <td style={{ padding: '14px 16px' }}>
                            <div style={{ fontWeight: 600, color: 'var(--on-surface)' }}>{item.display_name}</div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--on-surface-subtle)' }}>{item.email}</div>
                          </td>
                          <td style={{ padding: '14px 16px' }}>{fNum(item.proposals_sent_in_window)}</td>
                          <td style={{ padding: '14px 16px' }}>{item.avg_send_speed_per_day.toFixed(2)}/day</td>
                          <td style={{ padding: '14px 16px' }}>{fNum(item.total_jobs_sent_all_time)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { getUsageSummary, type UsageSummaryResponse } from '../lib/api'

// formatting utilities
const fNum = (n: number) => new Intl.NumberFormat('en-US').format(n)
const fUsd = (n: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n)

export function UsagePage() {
  const [data, setData] = useState<UsageSummaryResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [windowDays, setWindowDays] = useState<number>(30)

  useEffect(() => {
    let active = true
    setLoading(true)
    getUsageSummary(windowDays)
      .then(r => {
        if (active) {
          setData(r)
          setLoading(false)
        }
      })
      .catch((e) => {
        console.error(e)
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [windowDays])

  const StatCard = ({ label, value, sub }: { label: string, value: React.ReactNode, sub?: string }) => (
    <div className="card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--on-surface-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {label}
      </div>
      <div style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--on-surface)' }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: '0.75rem', color: 'var(--on-surface-subtle)' }}>{sub}</div>}
    </div>
  )

  return (
    <div className="page-container" style={{ padding: '32px 40px', overflowY: 'auto', height: '100%' }}>
      <div style={{ maxWidth: 900, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 32 }}>
        
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <p className="page-eyebrow">Analytics</p>
            <h1 className="page-title">Usage & Costs</h1>
            <p className="page-sub">Track AI generation workload and active token costs.</p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--on-surface-muted)' }}>Timeframe:</span>
            <select 
              className="input btn-pill" 
              style={{ width: 'auto', paddingRight: '36px', height: '36px', fontSize: '0.8125rem' }}
              value={windowDays}
              onChange={e => setWindowDays(Number(e.target.value))}
            >
              <option value="7">Last 7 days</option>
              <option value="30">Last 30 days</option>
              <option value="90">Last 90 days</option>
              <option value="365">Last year</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--on-surface-muted)' }}>Loading usage data...</div>
        ) : !data ? (
          <div className="card" style={{ padding: '40px', textAlign: 'center', color: 'var(--danger)' }}>Failed to load usage data.</div>
        ) : (
          <>
            {/* My Usage */}
            <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <h2 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--on-surface)' }}>My Usage</h2>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
                <StatCard 
                  label="Total Output Tokens" 
                  value={fNum(data.current_user.totals.output_tokens_total)} 
                  sub={`+ ${fNum(data.current_user.totals.input_tokens_total)} input tokens`}
                />
                <StatCard 
                  label="Successful Runs" 
                  value={fNum(data.current_user.totals.runs_success)} 
                  sub={`${fNum(data.current_user.totals.runs_failed)} failed runs`}
                />
                <StatCard 
                  label="Estimated Cost" 
                  value={fUsd(data.current_user.totals.estimated_cost_usd_total)} 
                  sub="Based on standard model pricing"
                />
              </div>
            </section>

            <div style={{ height: 1, background: 'var(--border)' }} />

            {/* Team Totals */}
            <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px' }}>
                <h2 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--on-surface)' }}>Team Summary</h2>
                <span style={{ fontSize: '0.8125rem', color: 'var(--primary)', background: 'var(--primary-glow)', padding: '2px 8px', borderRadius: '4px', fontWeight: 600 }}>
                  {data.active_user_count} active users
                </span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
                <StatCard 
                  label="Team Output Tokens" 
                  value={fNum(data.team_totals.output_tokens_total)} 
                  sub={`+ ${fNum(data.team_totals.input_tokens_total)} input tokens`}
                />
                <StatCard 
                  label="Team Runs" 
                  value={fNum(data.team_totals.runs_success)} 
                  sub={`${fNum(data.team_totals.runs_failed)} failed runs`}
                />
                <StatCard 
                  label="Team Cost" 
                  value={fUsd(data.team_totals.estimated_cost_usd_total)} 
                  sub={`Total from ${data.team_user_count} members`}
                />
              </div>
            </section>

            {/* Team Leaderboard */}
            <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <h2 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--on-surface)' }}>Usage Leaderboard</h2>
              <div className="card" style={{ overflow: 'hidden' }}>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', minWidth: 600, borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
                    <thead>
                      <tr style={{ background: 'rgba(255,255,255,0.02)', borderBottom: '1px solid var(--border)' }}>
                        <th style={{ padding: '16px 20px', color: 'var(--on-surface-muted)', fontWeight: 600 }}>User</th>
                        <th style={{ padding: '16px 20px', color: 'var(--on-surface-muted)', fontWeight: 600 }}>Runs</th>
                        <th style={{ padding: '16px 20px', color: 'var(--on-surface-muted)', fontWeight: 600 }}>Tokens (Out / In)</th>
                        <th style={{ padding: '16px 20px', color: 'var(--on-surface-muted)', fontWeight: 600, textAlign: 'right' }}>Cost</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.team_users
                        .sort((a, b) => b.totals.estimated_cost_usd_total - a.totals.estimated_cost_usd_total)
                        .map((u, i) => (
                          <tr key={u.user_id} style={{ borderBottom: i < data.team_users.length - 1 ? '1px solid var(--border)' : 'none' }}>
                            <td style={{ padding: '16px 20px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                              <div style={{ 
                                width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
                                background: 'rgba(255,255,255,0.05)', 
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                fontSize: '0.75rem', fontWeight: 700, color: 'var(--on-surface)'
                              }}>
                                {u.display_name.substring(0, 2).toUpperCase() || '?'}
                              </div>
                              <div>
                                <div style={{ fontWeight: 600, color: 'var(--on-surface)' }}>{u.display_name}</div>
                                <div style={{ fontSize: '0.75rem', color: 'var(--on-surface-subtle)' }}>{u.email}</div>
                              </div>
                            </td>
                            <td style={{ padding: '16px 20px' }}>
                              {fNum(u.totals.runs_success)} <span style={{ color: 'var(--on-surface-subtle)' }}>/ {fNum(u.totals.runs_total)}</span>
                            </td>
                            <td style={{ padding: '16px 20px' }}>
                              {fNum(u.totals.output_tokens_total)} <span style={{ color: 'var(--on-surface-subtle)' }}>/ {fNum(u.totals.input_tokens_total)}</span>
                            </td>
                            <td style={{ padding: '16px 20px', textAlign: 'right', fontWeight: 600, color: 'var(--primary)' }}>
                              {fUsd(u.totals.estimated_cost_usd_total)}
                            </td>
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

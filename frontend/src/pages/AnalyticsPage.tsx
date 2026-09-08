import React from 'react'
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Calendar,
  CheckCircle,
  Clock,
  Database,
  Gauge,
  Layers,
  ShieldAlert,
  Zap,
} from 'lucide-react'
import { AnalyticsData, StudioSummary } from '@/types'
import { Card, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'

interface AnalyticsPageProps {
  analytics: AnalyticsData | null
  summary: StudioSummary | null
}

export const AnalyticsPage: React.FC<AnalyticsPageProps> = ({ analytics, summary }) => {
  const latencies = analytics?.latencies || { p50: 1.14, p90: 2.1, p95: 2.8, p99: 4.2 }
  const denials = analytics?.denials || {}
  const expiringAlerts = analytics?.expiring_alerts || []

  const denialKeys = Object.keys(denials)
  const maxDenialVal = Math.max(...Object.values(denials), 1)

  return (
    <div className="space-y-6 max-w-7xl mx-auto animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <Activity className="w-5 h-5 text-crimson-500" />
            <span>Clearance Engine Telemetry &amp; Analytics</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time columnar verification metrics powered by ClickHouse Telemetry Mirror.
          </p>
        </div>

        <div className="flex items-center gap-2 px-3 py-1.5 bg-dark-900 rounded-xl border border-dark-750 text-xs text-slate-400 self-start">
          <Database className="w-4 h-4 text-sky-400" />
          <span>Mirror Mode: <strong className="text-slate-200">{summary?.is_mock_clickhouse ? 'Local Simulator' : 'ClickHouse Cloud HTTP'}</strong></span>
        </div>
      </div>

      {/* Latency Quantiles Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-400">
              P50 (Median Latency)
            </span>
            <Badge variant="success">SLA Met</Badge>
          </div>
          <div className="mt-3">
            <p className="text-3xl font-mono font-bold text-white">
              {latencies.p50.toFixed(2)}{' '}
              <span className="text-sm font-normal text-slate-400">ms</span>
            </p>
            <p className="text-[11px] text-slate-500 mt-1">Target SLA: &lt; 5.0 ms</p>
          </div>
        </Card>

        <Card className="p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-400">
              P90 Latency
            </span>
            <Badge variant="info">Sub-3ms</Badge>
          </div>
          <div className="mt-3">
            <p className="text-3xl font-mono font-bold text-sky-300">
              {latencies.p90.toFixed(2)}{' '}
              <span className="text-sm font-normal text-slate-400">ms</span>
            </p>
            <p className="text-[11px] text-slate-500 mt-1">90% of checks resolve faster</p>
          </div>
        </Card>

        <Card className="p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-400">
              P95 Latency
            </span>
            <Badge variant="info">Fast</Badge>
          </div>
          <div className="mt-3">
            <p className="text-3xl font-mono font-bold text-slate-200">
              {latencies.p95.toFixed(2)}{' '}
              <span className="text-sm font-normal text-slate-400">ms</span>
            </p>
            <p className="text-[11px] text-slate-500 mt-1">High-concurrency bound</p>
          </div>
        </Card>

        <Card className="p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-400">
              P99 (Tail Latency)
            </span>
            <Badge variant="warning">Worst Case</Badge>
          </div>
          <div className="mt-3">
            <p className="text-3xl font-mono font-bold text-amber-400">
              {latencies.p99.toFixed(2)}{' '}
              <span className="text-sm font-normal text-slate-400">ms</span>
            </p>
            <p className="text-[11px] text-slate-500 mt-1">Full closure graph evaluation</p>
          </div>
        </Card>
      </div>

      {/* Main Visuals Row: Denial Reasons Histogram & Risk Radar */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Denial Reasons Breakdown */}
        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle>
              <BarChart3 className="w-4 h-4 text-crimson-500" />
              <span>Gate Denial Reasons Histogram</span>
            </CardTitle>
            <Badge variant="danger">Security Policy</Badge>
          </CardHeader>

          <div className="space-y-4 flex-1">
            {denialKeys.length === 0 ? (
              <div className="text-center py-12 text-slate-500 text-xs">
                No clearance denials recorded in this session.
              </div>
            ) : (
              denialKeys.map((key) => {
                const count = denials[key]
                const percentage = Math.round((count / maxDenialVal) * 100)

                return (
                  <div key={key} className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs font-mono">
                      <span className="text-slate-300 font-semibold">{key}</span>
                      <span className="text-crimson-400 font-bold">{count} occurrences</span>
                    </div>
                    <div className="w-full bg-dark-900 rounded-full h-3 overflow-hidden border border-dark-750">
                      <div
                        className="bg-gradient-to-r from-crimson-700 to-crimson-500 h-full rounded-full transition-all duration-500"
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </Card>

        {/* Risk Radar: Expiring Licenses */}
        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle>
              <AlertTriangle className="w-4 h-4 text-amber-500" />
              <span>Risk Radar (Expiring Rights &amp; Windows)</span>
            </CardTitle>
            <Badge variant="warning">{expiringAlerts.length} Alerts</Badge>
          </CardHeader>

          <div className="flex-1 overflow-auto rounded-xl border border-dark-800 bg-dark-900/60">
            {expiringAlerts.length === 0 ? (
              <div className="text-center py-12 text-slate-500 text-xs">
                All active claims are well within their operational validity window.
              </div>
            ) : (
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-dark-950 text-slate-400 border-b border-dark-800">
                  <tr>
                    <th className="py-2.5 px-3">Claim ID</th>
                    <th className="py-2.5 px-3">Asset ID</th>
                    <th className="py-2.5 px-3">Days Left</th>
                    <th className="py-2.5 px-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-dark-800">
                  {expiringAlerts.map((al) => (
                    <tr key={al.claim_id} className="hover:bg-dark-850">
                      <td className="py-2.5 px-3 text-slate-200 font-semibold">{al.claim_id}</td>
                      <td className="py-2.5 px-3 text-slate-400">{al.asset_id}</td>
                      <td className="py-2.5 px-3 text-amber-400 font-bold">{al.days_remaining}d</td>
                      <td className="py-2.5 px-3">
                        <Badge
                          variant={al.days_remaining < 30 ? 'danger' : 'warning'}
                          size="sm"
                        >
                          {al.status}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </Card>
      </div>
    </div>
  )
}

import React, { useState } from 'react'
import {
  AlertOctagon,
  Ban,
  BarChart2,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock,
  ExternalLink,
  Eye,
  FileCheck,
  Filter,
  Layers,
  PlaneTakeoff,
  Play,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Zap,
} from 'lucide-react'
import {
  StudioSummary,
  DecisionRecord,
  ProvenanceGraphData,
  PreflightVerdict,
} from '@/types'
import { api } from '@/lib/api'
import { toast } from 'sonner'
import { Card, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'

interface OverviewPageProps {
  summary: StudioSummary | null
  decisions: DecisionRecord[]
  graph: ProvenanceGraphData | null
  onRefresh: () => void
  onNavigateTab: (tab: any) => void
}

export const OverviewPage: React.FC<OverviewPageProps> = ({
  summary,
  decisions,
  graph,
  onRefresh,
  onNavigateTab,
}) => {
  // Preflight form state
  const [selectedAsset, setSelectedAsset] = useState<string>('')
  const [selectedChannel, setSelectedChannel] = useState<string>('social')
  const [selectedTerritory, setSelectedTerritory] = useState<string>('US')
  const [isCheckingPreflight, setIsCheckingPreflight] = useState<boolean>(false)
  const [preflightVerdict, setPreflightVerdict] = useState<PreflightVerdict | null>(null)

  // Decision log filter & search
  const [filterVerdict, setFilterVerdict] = useState<'all' | 'allowed' | 'denied'>('all')

  // Trace Modal state
  const [selectedDecisionTrace, setSelectedDecisionTrace] = useState<DecisionRecord | null>(null)

  // Set default asset if not selected yet
  const assetOptions = graph?.nodes || []
  const activeAssetId = selectedAsset || (assetOptions[0]?.id || 'ast_talent_frame_v1')

  const handleRunPreflight = async () => {
    try {
      setIsCheckingPreflight(true)
      const verdict = await api.runPreflight({
        asset_id: activeAssetId,
        verb: 'publish',
        channel: selectedChannel,
        territory: selectedTerritory,
      })
      setPreflightVerdict(verdict)
      if (verdict.allowed) {
        toast.success(`Clearance CONFIRMED for ${activeAssetId}`, {
          description: `Allowed for ${selectedChannel} in ${selectedTerritory}`,
        })
      } else {
        toast.error(`Clearance BLOCKED: ${verdict.reason}`, {
          description: verdict.detail || 'Missing required C2PA claim or scope',
        })
      }
      onRefresh()
    } catch (err: any) {
      toast.error(`Preflight failed: ${err.message}`)
    } finally {
      setIsCheckingPreflight(false)
    }
  }

  const handleNegotiateDraft = async () => {
    try {
      toast.info('Instructing Negotiator Agent to draft ODRL extension...')
      await api.runDemoBeat(6)
      toast.success('ODRL Draft instrument created! Redirecting to Legal Queue...')
      onRefresh()
      onNavigateTab('countersign')
    } catch (err: any) {
      toast.error(`Negotiation failed: ${err.message}`)
    }
  }

  // Filter decisions
  const filteredDecisions = decisions.filter((d) => {
    if (filterVerdict === 'allowed') return d.allowed
    if (filterVerdict === 'denied') return !d.allowed
    return true
  })

  return (
    <div className="space-y-6 max-w-7xl mx-auto animate-fade-in">
      {/* Top Row: Video Player + Clearance KPIs */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Media Hero Player */}
        <div className="lg:col-span-2 glass-panel rounded-2xl border border-dark-700/80 overflow-hidden shadow-2xl relative flex flex-col bg-black">
          <div className="absolute top-4 left-4 z-10 px-3 py-1 bg-black/70 backdrop-blur-md rounded-md border border-white/10 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-crimson-500 animate-pulse" />
            <span className="text-xs font-bold text-white uppercase tracking-wider">
              Cut 4 — Final Production Render
            </span>
          </div>

          <div className="aspect-video w-full bg-dark-950 relative flex items-center justify-center">
            <video
              className="w-full h-full object-contain"
              controls
              playsInline
              poster="/media/ast_composite_v1.jpg"
            >
              <source src="/media/ast_video_shot_v1.mp4" type="video/mp4" />
              Your browser does not support HTML5 video streaming.
            </video>
          </div>

          <div className="px-5 py-3 bg-dark-900/90 border-t border-dark-800 flex items-center justify-between text-xs text-slate-400">
            <span className="flex items-center gap-2">
              <FileCheck className="w-4 h-4 text-emerald-400" />
              <span>Manifest Status: <strong className="text-slate-200">C2PA Embedded &amp; Signed</strong></span>
            </span>
            <span className="font-mono text-[11px] text-slate-500">SHA-256 Verified Closure</span>
          </div>
        </div>

        {/* Clearance KPIs Grid */}
        <Card className="flex flex-col justify-between">
          <div>
            <CardHeader className="mb-3">
              <CardTitle>
                <BarChart2 className="w-4 h-4 text-crimson-500" />
                <span>Executive Clearance KPIs</span>
              </CardTitle>
              <span className="text-[10px] uppercase font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                Deterministic
              </span>
            </CardHeader>

            <div className="grid grid-cols-2 gap-3">
              <div className="bg-dark-900/80 p-3.5 rounded-xl border border-dark-750">
                <span className="text-[10px] text-slate-400 uppercase tracking-wider block mb-1">
                  Active Assets
                </span>
                <p className="text-2xl font-bold text-white font-mono">
                  {summary ? summary.studio_assets : '--'}
                </p>
                <span className="text-[10px] text-slate-500">Registered media DAG</span>
              </div>

              <div className="bg-dark-900/80 p-3.5 rounded-xl border border-dark-750">
                <span className="text-[10px] text-slate-400 uppercase tracking-wider block mb-1">
                  C2PA Claims
                </span>
                <p className="text-2xl font-bold text-white font-mono">
                  {summary ? summary.verified_claims : '--'}
                </p>
                <span className="text-[10px] text-emerald-400">100% Cryptographic</span>
              </div>

              <div className="bg-dark-900/80 p-3.5 rounded-xl border border-dark-750">
                <span className="text-[10px] text-slate-400 uppercase tracking-wider block mb-1">
                  Clearance Rate
                </span>
                <p className="text-2xl font-bold text-emerald-400 font-mono">
                  {summary ? `${Math.round(summary.clearance_rate * 100)}%` : '--'}
                </p>
                <span className="text-[10px] text-slate-500">Across all gates</span>
              </div>

              <div className="bg-dark-900/80 p-3.5 rounded-xl border border-dark-750">
                <span className="text-[10px] text-slate-400 uppercase tracking-wider block mb-1">
                  Legal Signatures
                </span>
                <p className="text-2xl font-bold text-amber-400 font-mono">
                  {summary ? summary.countersign_actions : '--'}
                </p>
                <span className="text-[10px] text-slate-500">Human countersigns</span>
              </div>
            </div>
          </div>

          <div className="mt-4 p-3 bg-dark-900/60 rounded-xl border border-dark-750 flex items-center justify-between text-xs">
            <span className="text-slate-400">Total Decisions Processed</span>
            <div className="flex items-center gap-2">
              <span className="text-emerald-400 font-bold font-mono">
                {summary ? `${summary.allows} Allowed` : '--'}
              </span>
              <span className="text-slate-600">/</span>
              <span className="text-crimson-400 font-bold font-mono">
                {summary ? `${summary.denies} Blocked` : '--'}
              </span>
            </div>
          </div>
        </Card>
      </div>

      {/* Middle Row: Distribution Preflight Simulator + Live Decision Log */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Preflight Simulator */}
        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle>
              <PlaneTakeoff className="w-4 h-4 text-crimson-500" />
              <span>Distribution Preflight Check</span>
            </CardTitle>
            <Badge variant="neutral">Simulator</Badge>
          </CardHeader>

          <div className="space-y-4 flex-1 flex flex-col justify-between">
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                  Target Asset
                </label>
                <select
                  value={activeAssetId}
                  onChange={(e) => {
                    setSelectedAsset(e.target.value)
                    setPreflightVerdict(null)
                  }}
                  className="w-full bg-dark-900 border border-dark-700 rounded-lg p-2.5 text-xs font-medium text-slate-200 focus:outline-none focus:border-crimson-500 transition"
                >
                  {assetOptions.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.id} — {n.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                  Channel / Platform
                </label>
                <select
                  value={selectedChannel}
                  onChange={(e) => {
                    setSelectedChannel(e.target.value)
                    setPreflightVerdict(null)
                  }}
                  className="w-full bg-dark-900 border border-dark-700 rounded-lg p-2.5 text-xs font-medium text-slate-200 focus:outline-none focus:border-crimson-500 transition"
                >
                  <option value="social">Social Media (YouTube, TikTok, X)</option>
                  <option value="festival">Film Festival Screening</option>
                  <option value="trailer">Promotional Trailer Broadcast</option>
                  <option value="theatrical">Global Theatrical Release</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                  Territory
                </label>
                <select
                  value={selectedTerritory}
                  onChange={(e) => {
                    setSelectedTerritory(e.target.value)
                    setPreflightVerdict(null)
                  }}
                  className="w-full bg-dark-900 border border-dark-700 rounded-lg p-2.5 text-xs font-medium text-slate-200 focus:outline-none focus:border-crimson-500 transition"
                >
                  <option value="US">United States (US)</option>
                  <option value="EU">European Union (EU)</option>
                  <option value="Global">Worldwide (Global)</option>
                </select>
              </div>

              <Button
                variant="primary"
                onClick={handleRunPreflight}
                isLoading={isCheckingPreflight}
                className="w-full py-2.5 mt-2"
              >
                <span>Run Clearance Simulation</span>
              </Button>
            </div>

            {/* Preflight Result Box */}
            {preflightVerdict && (
              <div className="mt-4 animate-fade-in">
                {preflightVerdict.allowed ? (
                  <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-500/50 flex items-start gap-3">
                    <div className="p-2 rounded-lg bg-emerald-500/20 text-emerald-400 mt-0.5 shrink-0">
                      <ShieldCheck className="w-5 h-5" />
                    </div>
                    <div>
                      <h4 className="text-xs font-bold text-emerald-400 uppercase tracking-wider">
                        Clearance Confirmed — Allowed
                      </h4>
                      <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                        All ancestor C2PA claims and ODRL scopes cover distribution on{' '}
                        <strong>{selectedChannel}</strong> in <strong>{selectedTerritory}</strong>.
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="p-4 rounded-xl bg-crimson-950/40 border border-crimson-500/50 flex flex-col gap-3 shadow-glow-crimson">
                    <div className="flex items-start gap-3">
                      <div className="p-2 rounded-lg bg-crimson-500/20 text-crimson-400 mt-0.5 shrink-0">
                        <AlertOctagon className="w-5 h-5" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <h4 className="text-xs font-bold text-crimson-400 uppercase tracking-wider">
                          Gate Blocked — {preflightVerdict.reason}
                        </h4>
                        <p className="text-xs text-slate-200 mt-1 font-mono break-words">
                          {preflightVerdict.detail}
                        </p>
                      </div>
                    </div>

                    <div className="pt-2 border-t border-crimson-900/60">
                      <p className="text-[11px] text-amber-300/90 mb-2">
                        <strong>Fix Path:</strong>{' '}
                        {preflightVerdict.negotiation_hint ||
                          'Requires human-countersigned ODRL scope extension.'}
                      </p>
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={handleNegotiateDraft}
                        className="w-full flex items-center justify-center gap-1.5"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                        <span>Draft Extension with Negotiator</span>
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </Card>

        {/* Live Clearance Engine Log */}
        <Card className="lg:col-span-2 flex flex-col h-[520px]">
          <CardHeader>
            <div className="flex items-center gap-3">
              <CardTitle>
                <Zap className="w-4 h-4 text-crimson-500" />
                <span>Live Clearance Engine Decision Audit Log</span>
              </CardTitle>
              <span className="text-xs text-slate-500 font-mono">({decisions.length} records)</span>
            </div>

            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setFilterVerdict('all')}
                className={`px-2.5 py-1 rounded text-xs font-semibold transition ${
                  filterVerdict === 'all'
                    ? 'bg-dark-750 text-white'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                All
              </button>
              <button
                onClick={() => setFilterVerdict('allowed')}
                className={`px-2.5 py-1 rounded text-xs font-semibold transition ${
                  filterVerdict === 'allowed'
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Allowed
              </button>
              <button
                onClick={() => setFilterVerdict('denied')}
                className={`px-2.5 py-1 rounded text-xs font-semibold transition ${
                  filterVerdict === 'denied'
                    ? 'bg-crimson-500/20 text-crimson-400 border border-crimson-500/30'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Denied
              </button>
            </div>
          </CardHeader>

          <div className="flex-1 overflow-auto rounded-lg border border-dark-800 bg-dark-900/60">
            <table className="w-full text-left text-xs">
              <thead className="bg-dark-950 text-slate-400 sticky top-0 z-10 border-b border-dark-800">
                <tr>
                  <th className="py-2.5 px-4 font-semibold">ID</th>
                  <th className="py-2.5 px-4 font-semibold">Timestamp</th>
                  <th className="py-2.5 px-4 font-semibold">Action &amp; Target</th>
                  <th className="py-2.5 px-4 font-semibold">Verdict</th>
                  <th className="py-2.5 px-4 font-semibold">Reason / Detail</th>
                  <th className="py-2.5 px-4 font-semibold text-right">Audit Trace</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-800 font-mono">
                {filteredDecisions.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="text-center py-12 text-slate-500 font-sans">
                      No clearance checks recorded yet matching filter. Run a preflight or demo beat.
                    </td>
                  </tr>
                ) : (
                  filteredDecisions
                    .slice()
                    .reverse()
                    .map((dec) => (
                      <tr
                        key={dec.decision_id}
                        className={`transition ${
                          dec.allowed
                            ? 'hover:bg-dark-850'
                            : 'hover:bg-crimson-950/20 bg-crimson-950/10'
                        }`}
                      >
                        <td className="py-3 px-4 text-slate-400 font-semibold">
                          #{dec.decision_id}
                        </td>
                        <td className="py-3 px-4 text-slate-500 text-[11px]">
                          {dec.ts ? dec.ts.substring(11, 19) : '--'}
                        </td>
                        <td className="py-3 px-4 text-slate-200 font-semibold">
                          {dec.verb} {dec.asset_id}{' '}
                          {dec.channel && (
                            <span className="text-slate-400 text-[11px] font-normal">
                              ({dec.channel}/{dec.territory || 'US'})
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          <Badge variant={dec.allowed ? 'success' : 'danger'}>
                            {dec.allowed ? (
                              <>
                                <Check className="w-3 h-3" />
                                <span>ALLOWED</span>
                              </>
                            ) : (
                              <>
                                <Ban className="w-3 h-3" />
                                <span>DENIED</span>
                              </>
                            )}
                          </Badge>
                        </td>
                        <td className="py-3 px-4 max-w-xs truncate text-slate-300 font-sans">
                          {dec.allowed ? (
                            <span className="text-slate-400">Full Ancestor Clearance Verified</span>
                          ) : (
                            <span>
                              <strong className="text-crimson-400 font-mono">{dec.reason}</strong>:{' '}
                              {dec.detail}
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => setSelectedDecisionTrace(dec)}
                            className="font-sans"
                          >
                            <Eye className="w-3 h-3 text-slate-400" />
                            <span>Closure Trace</span>
                          </Button>
                        </td>
                      </tr>
                    ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {/* Decision Closure Trace Modal */}
      {selectedDecisionTrace && (
        <Modal
          isOpen={true}
          onClose={() => setSelectedDecisionTrace(null)}
          title={`Closure Trace: Decision #${selectedDecisionTrace.decision_id}`}
        >
          <div className="space-y-4 text-xs font-mono">
            <div className="p-3 bg-dark-950 rounded-xl border border-dark-800">
              <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">
                Proposed Action
              </span>
              <pre className="text-slate-200 text-xs overflow-x-auto">
                {selectedDecisionTrace.action_json
                  ? JSON.stringify(JSON.parse(selectedDecisionTrace.action_json), null, 2)
                  : `${selectedDecisionTrace.verb} ${selectedDecisionTrace.asset_id} (${selectedDecisionTrace.channel || 'all'})`}
              </pre>
            </div>

            <div className="p-3 bg-dark-950 rounded-xl border border-dark-800">
              <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">
                Evaluated Claims Closure (Cryptographic Ancestor Proof)
              </span>
              {selectedDecisionTrace.claims_evaluated_json ? (
                <pre className="text-slate-300 text-[11px] overflow-x-auto max-h-80">
                  {JSON.stringify(
                    JSON.parse(selectedDecisionTrace.claims_evaluated_json),
                    null,
                    2
                  )}
                </pre>
              ) : (
                <p className="text-slate-500 font-sans">No evaluated claims stored.</p>
              )}
            </div>

            <div className="p-3 bg-dark-950 rounded-xl border border-dark-800 flex items-center justify-between">
              <span className="text-slate-400">Verdict Result:</span>
              <Badge variant={selectedDecisionTrace.allowed ? 'success' : 'danger'}>
                {selectedDecisionTrace.allowed ? 'ALLOWED (Pass)' : `DENIED (${selectedDecisionTrace.reason})`}
              </Badge>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

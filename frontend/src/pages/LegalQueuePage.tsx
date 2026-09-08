import React, { useState } from 'react'
import {
  CheckCircle2,
  Clock,
  FileCode,
  FileSignature,
  FileText,
  Lock,
  PenTool,
  Shield,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { PendingDraft } from '@/types'
import { api } from '@/lib/api'
import { toast } from 'sonner'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'

interface LegalQueuePageProps {
  pendingDrafts: PendingDraft[]
  onRefresh: () => void
  onNavigateTab?: (tab: string) => void
}

export const LegalQueuePage: React.FC<LegalQueuePageProps> = ({
  pendingDrafts,
  onRefresh,
}) => {
  const [approvingDraftId, setApprovingDraftId] = useState<string | null>(null)

  const handleApprove = async (draftId: string) => {
    try {
      setApprovingDraftId(draftId)
      const res = await api.approveDraft(draftId, 'Elena Vance (Studio Legal Lead)')
      if (res.ok) {
        toast.success(`Instrument Approved! Signed into Rights Graph`, {
          description: `Cryptographic Claim ID: ${res.claim_id}`,
          duration: 4000,
        })
        onRefresh()
      }
    } catch (err: any) {
      toast.error(`Approval failed: ${err.message}`)
    } finally {
      setApprovingDraftId(null)
    }
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto animate-fade-in">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-crimson-600/15 border border-crimson-500/30 text-crimson-400">
              <PenTool className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
                <span>Legal Countersign Queue</span>
                {pendingDrafts.length > 0 && (
                  <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30">
                    {pendingDrafts.length} Pending
                  </span>
                )}
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Invariant 6: Agents propose ODRL license instruments; only human legal signatures mint
                executable rights.
              </p>
            </div>
          </div>
        </div>

        <div className="px-3.5 py-2 rounded-xl bg-dark-900 border border-dark-750 flex items-center gap-2 text-xs text-slate-400 self-start">
          <Lock className="w-4 h-4 text-amber-400" />
          <span>Authorized Signer: <strong className="text-slate-200">Elena Vance</strong></span>
        </div>
      </div>

      {/* Queue items */}
      <div className="space-y-5">
        {pendingDrafts.length === 0 ? (
          <Card className="text-center py-16 flex flex-col items-center justify-center">
            <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 mb-3">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <h3 className="text-base font-bold text-slate-100">
              No Pending Instruments in Legal Queue
            </h3>
            <p className="text-xs text-slate-400 max-w-md mt-1.5 leading-relaxed">
              All agent proposals are fully countersigned and bound into the rights graph. When a
              clearance gate denial occurs during production, the autonomous Negotiator will place new
              ODRL drafts here for human review.
            </p>
          </Card>
        ) : (
          pendingDrafts.map((item) => {
            let parsedOdrl: any = {}
            try {
              parsedOdrl = JSON.parse(item.odrl_json)
            } catch {
              parsedOdrl = item.odrl_json
            }

            return (
              <Card
                key={item.draft_id}
                className="border-amber-500/40 relative overflow-hidden shadow-2xl"
              >
                {/* Card Top Banner */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-dark-750">
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-xl bg-amber-500/15 text-amber-400 border border-amber-500/30">
                      <FileSignature className="w-5 h-5" />
                    </div>
                    <div>
                      <h4 className="text-sm font-mono font-bold text-white tracking-wide">
                        {item.draft_id}
                      </h4>
                      <p className="text-xs text-slate-400">
                        Target Asset: <strong className="text-slate-200 font-mono">{item.asset_id}</strong>{' '}
                        <span className="text-slate-500">({item.kind})</span>
                      </p>
                    </div>
                  </div>

                  <Badge variant="warning" size="md">
                    <Clock className="w-3.5 h-3.5" />
                    <span>PENDING HUMAN SIGNATURE</span>
                  </Badge>
                </div>

                {/* Card Body: Summary + ODRL Payload */}
                <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  <div className="p-4 rounded-xl bg-dark-900 border border-dark-750 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <FileText className="w-4 h-4 text-crimson-400" />
                        <span className="font-bold text-slate-300 uppercase tracking-wider text-[10px]">
                          Executive Legal Summary
                        </span>
                      </div>
                      <p className="text-slate-200 leading-relaxed font-sans">{item.summary}</p>
                    </div>

                    <div className="mt-4 pt-3 border-t border-dark-800 text-[11px] text-slate-400">
                      <span>Authority: </span>
                      <strong className="text-slate-200">Elena Vance (Studio Legal Lead)</strong>
                    </div>
                  </div>

                  <div className="p-4 rounded-xl bg-dark-900 border border-dark-750 font-mono">
                    <div className="flex items-center gap-2 mb-2">
                      <FileCode className="w-4 h-4 text-sky-400" />
                      <span className="font-bold text-slate-300 uppercase tracking-wider text-[10px]">
                        W3C ODRL 2.2 Permissions Payload
                      </span>
                    </div>
                    <pre className="text-slate-300 overflow-x-auto text-[11px] max-h-48 bg-dark-950 p-2.5 rounded-lg border border-dark-800">
                      {JSON.stringify(parsedOdrl, null, 2)}
                    </pre>
                  </div>
                </div>

                {/* Card Action Footer */}
                <div className="mt-5 pt-4 border-t border-dark-750 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="text-xs text-slate-400 flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-emerald-400" />
                    <span>Signing writes an authoritative cryptographic claim into SQLite graph</span>
                  </div>

                  <Button
                    variant="success"
                    size="md"
                    onClick={() => handleApprove(item.draft_id)}
                    isLoading={approvingDraftId === item.draft_id}
                    className="shadow-glow-emerald"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Countersign &amp; Bind Rights</span>
                  </Button>
                </div>
              </Card>
            )
          })
        )}
      </div>
    </div>
  )
}

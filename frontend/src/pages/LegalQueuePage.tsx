import { useState } from 'react'
import { ArrowRight, CheckCircle2, Clock3, FileSignature, ShieldCheck, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import type { PendingDraft } from '@/types'
import type { TabType } from '@/components/layout/Sidebar'
import { api, assetName, readableJson } from '@/lib/api'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
interface Props { pendingDrafts: PendingDraft[]; onRefresh: () => void; onNavigateTab: (tab: TabType) => void }
export function LegalQueuePage({ pendingDrafts, onRefresh, onNavigateTab }: Props) {
  const [review, setReview] = useState<PendingDraft | null>(null)
  const [signer, setSigner] = useState('')
  const [consent, setConsent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const approve = async () => {
    if (!review || !consent || signer.trim().length < 2 || busy) return
    setBusy(true); setError('')
    try { await api.approveDraft(review.draft_id, signer.trim()); toast.success('Sample permission approved', { description: 'The rights records have been updated. Run a new check to evaluate the change.' }); setReview(null); onRefresh() }
    catch { setError('We couldn’t confirm this approval. Refresh the workspace before retrying; the request may have reached the server.') }
    finally { setBusy(false) }
  }
  return <div className="page-stack"><div className="page-heading"><div><span className="eyebrow">HUMAN JUDGMENT. ALWAYS.</span><h1>The next step is yours.</h1><p>Review proposed license changes before they become recorded permissions.</p></div><Badge variant={pendingDrafts.length ? 'warning' : 'success'} size="md"><Clock3 size={14} />{pendingDrafts.length} awaiting review</Badge></div><div className="notice"><ShieldCheck size={22} /><div><strong>You’re in control of every approval</strong><p>AI can help draft a request, but it cannot approve one here. Review the terms and explicitly confirm any change. This sample workspace has no authenticated signing identity.</p></div></div>
    {!pendingDrafts.length ? <div className="card approval-empty"><span className="empty-approval-icon"><CheckCircle2 size={38} /></span><h2>All clear on your to-do list.</h2><p>No license changes are waiting for review. If a clearance check identifies missing rights, work with your rights team to arrange the appropriate permission.</p><Button variant="secondary" onClick={() => onNavigateTab('examples')}>Explore a clearance example <ArrowRight size={15} /></Button></div> : pendingDrafts.map(d => <article className="card approval-card" key={d.draft_id}><div className="approval-top"><span className="approval-icon"><FileSignature size={24} /></span><div><span className="eyebrow">PROPOSED LICENSE CHANGE</span><h2>{assetName(d.asset_id)}</h2></div><Badge variant="warning">Awaiting review</Badge></div><p>{d.summary}</p><details><summary>View proposed license terms</summary><pre>{readableJson(d.odrl_json)}</pre></details><div className="approval-footer"><span><Sparkles size={15} />Draft only · No permissions changed yet</span><Button onClick={() => { setReview(d); setSigner(''); setConsent(false); setError('') }}>Review & approve <ArrowRight size={15} /></Button></div></article>)}
    <Modal isOpen={!!review} onClose={() => { if (!busy) setReview(null) }} title="Review this permission change">{review && <><div className="inline-sample">Sample approval · Changes shared sample rights</div><h3>{assetName(review.asset_id)}</h3><p className="modal-intro">{review.summary}</p><details open><summary>License terms to review</summary><pre>{readableJson(review.odrl_json)}</pre></details><form onSubmit={e => { e.preventDefault(); void approve() }}><fieldset className="check-fields" disabled={busy}><label htmlFor="signer-name">Reviewer name (sample display name)<input id="signer-name" value={signer} onChange={e => setSigner(e.target.value)} placeholder="e.g. Sample reviewer" minLength={2} maxLength={100} required /></label><label className="checkbox-label"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} required /><span>I have reviewed these terms and understand that approving updates the shared sample rights records. This is not a real legal signature.</span></label>{error && <p className="form-error" role="alert">{error}</p>}<Button type="submit" disabled={!consent || signer.trim().length < 2} isLoading={busy} className="full-width"><FileSignature size={16} />Confirm sample approval</Button></fieldset></form></>}</Modal>
  </div>
}

import { useCallback, useEffect, useRef, useState } from 'react'
import { Toaster } from 'sonner'
import { AlertCircle, ArrowRight, BookOpen, CheckCircle2, FileCheck2, FolderOpen, ShieldCheck, Sparkles } from 'lucide-react'
import type { StudioSummary, DecisionRecord, ProvenanceGraphData, PendingDraft, AnalyticsData } from '@/types'
import { api } from '@/lib/api'
import { Header } from '@/components/layout/Header'
import { Sidebar, tabLabels, type TabType } from '@/components/layout/Sidebar'
import { OverviewPage } from '@/pages/OverviewPage'
import { LineagePage } from '@/pages/LineagePage'
import { LegalQueuePage } from '@/pages/LegalQueuePage'
import { AnalyticsPage } from '@/pages/AnalyticsPage'
import { CertificatePage } from '@/pages/CertificatePage'
import { Button } from '@/components/ui/Button'
const readTab = (): TabType => { const tab = window.location.hash.slice(1); return tab in tabLabels ? tab as TabType : 'overview' }
export function App() {
  const [activeTab, setActiveTab] = useState<TabType>(readTab)
  const [summary, setSummary] = useState<StudioSummary | null>(null)
  const [decisions, setDecisions] = useState<DecisionRecord[]>([])
  const [graph, setGraph] = useState<ProvenanceGraphData | null>(null)
  const [pendingDrafts, setPendingDrafts] = useState<PendingDraft[]>([])
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [networkError, setNetworkError] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const inFlight = useRef(false)
  const main = useRef<HTMLElement>(null)
  const navigate = (tab: TabType) => { window.location.hash = tab; setActiveTab(tab); setMobileOpen(false); main.current?.scrollTo(0, 0) }
  const loadData = useCallback(async () => {
    if (inFlight.current) return
    inFlight.current = true
    setRefreshing(true)
    try {
      const [sum, dec, gr, pend, an] = await Promise.all([api.getSummary(), api.getDecisions(), api.getGraph(), api.getPendingApprovals(), api.getAnalytics()])
      setSummary(sum); setDecisions(dec); setGraph(gr); setPendingDrafts(pend); setAnalytics(an); setNetworkError(false)
    } catch { setNetworkError(true) }
    finally { setIsLoading(false); setRefreshing(false); inFlight.current = false }
  }, [])
  useEffect(() => {
    void loadData()
    const interval = setInterval(() => { if (!document.hidden) void loadData() }, 15000)
    const onHash = () => { setActiveTab(readTab()); main.current?.scrollTo(0, 0) }
    window.addEventListener('hashchange', onHash)
    return () => { clearInterval(interval); window.removeEventListener('hashchange', onHash) }
  }, [loadData])
  return <div className="app-shell"><a className="skip-link" href="#main-content">Skip to content</a><Toaster theme="light" position="bottom-right" richColors closeButton />
    <Sidebar activeTab={activeTab} onSelectTab={navigate} summary={summary} isMobileOpen={mobileOpen} onCloseMobile={() => setMobileOpen(false)} />
    <div className="workspace-main"><Header activeTab={activeTab} onRefresh={loadData} refreshing={refreshing} connected={!!summary && !networkError} onToggleMobileSidebar={() => setMobileOpen(!mobileOpen)} onHelp={() => navigate('help')} />
      <main id="main-content" ref={main} tabIndex={-1} className="main-content">
        {isLoading ? <div className="loading-state" role="status"><span className="loading-mark"><ShieldCheck size={30} /></span><h2>Opening your workspace</h2><p>Gathering your assets, rights, and recent checks…</p><div className="skeleton-grid">{[1,2,3,4].map(n => <div key={n} />)}</div></div> : networkError ? <div className="error-state" role="alert"><AlertCircle size={36} /><h1>We couldn’t refresh your workspace</h1><p>Your actions haven’t been submitted. Check your connection and try again.</p><Button onClick={loadData} isLoading={refreshing}>Try again</Button></div> : <>
          {(activeTab === 'overview' || activeTab === 'examples') && <OverviewPage key={activeTab} summary={summary} decisions={decisions} graph={graph} onRefresh={loadData} onNavigateTab={navigate} examplesOnly={activeTab === 'examples'} />}
          {activeTab === 'provenance' && <LineagePage graph={graph} />}
          {activeTab === 'countersign' && <LegalQueuePage pendingDrafts={pendingDrafts} onRefresh={loadData} onNavigateTab={navigate} />}
          {activeTab === 'analytics' && <AnalyticsPage analytics={analytics} summary={summary} />}
          {activeTab === 'certificates' && <CertificatePage summary={summary} decisions={decisions} />}
          {activeTab === 'help' && <div className="page-stack"><div className="page-heading"><div><span className="eyebrow">A LITTLE GUIDANCE, A LOT OF CONFIDENCE</span><h1>Your first clearance, made simple.</h1><p>You don’t need to be a rights expert to get started.</p></div><BookOpen className="heading-icon" /></div><div className="help-grid">{[{ icon: FolderOpen, title: '1. Choose an asset', text: 'Browse the asset library to see the media in your workspace and the rights records attached to it.', tab: 'provenance' },{ icon: Sparkles, title: '2. Check before publishing', text: 'Choose where and how you want to use the asset. We check the recorded permissions, without publishing anything.', tab: 'examples' },{ icon: FileCheck2, title: '3. Review missing permissions', text: 'If a check is blocked, review the explanation with your rights team. License changes need an explicit human approval.', tab: 'countersign' },{ icon: ShieldCheck, title: '4. Keep an audit record', text: 'Download a dated report of recorded checks and permissions to share with your legal team. It is not an insurance policy.', tab: 'certificates' }].map(s => <div className="card help-card" key={s.title}><s.icon size={25} /><h2>{s.title}</h2><p>{s.text}</p><Button variant="ghost" onClick={() => navigate(s.tab as TabType)}>Explore <ArrowRight size={15} /></Button></div>)}</div><div className="notice"><CheckCircle2 size={20} /><div><strong>A safe place to learn</strong><p>This is a sample workspace with preloaded assets. Checks evaluate recorded rights and add an audit entry; they don’t upload or publish media. Sample approvals change this shared sample workspace, not a real legal agreement.</p></div></div><div className="card glossary"><h2>A few useful terms</h2><details><summary>What does “cleared” mean?</summary><p>The recorded permissions cover the specific action, channel, and territory you checked. It does not authorize every possible use or replace legal advice.</p></details><details><summary>What are content credentials (C2PA)?</summary><p>Signed records describing where a media asset came from. A trusted signature is one part of a clearance check, not a blanket guarantee of ownership.</p></details><details><summary>Why can a combined asset be blocked?</summary><p>A video inherits limits from its ingredients. For example, music licensed for a film festival may not be licensed for a public trailer.</p></details><details><summary>Is this ready for my company’s live media?</summary><p>Not yet. Production use requires authenticated accounts, permission-based signing, durable per-workspace storage, and operational security review. Do not enter sensitive information in this sample workspace.</p></details></div></div>}
        </>}
        <footer className="page-footer"><span><ShieldCheck size={14} /> Doctus · Clarity behind every creation.</span><span>Sample workspace <span className="footer-dot">·</span> Rights checks, not legal advice</span></footer>
      </main>
    </div>
  </div>
}
export default App

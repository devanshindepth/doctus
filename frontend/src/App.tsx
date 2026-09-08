import React, { useCallback, useEffect, useState } from 'react'
import { Toaster, toast } from 'sonner'
import {
  StudioSummary,
  DecisionRecord,
  ProvenanceGraphData,
  PendingDraft,
  AnalyticsData,
} from '@/types'
import { api } from '@/lib/api'
import { Header } from '@/components/layout/Header'
import { Sidebar, TabType } from '@/components/layout/Sidebar'
import { OverviewPage } from '@/pages/OverviewPage'
import { LineagePage } from '@/pages/LineagePage'
import { LegalQueuePage } from '@/pages/LegalQueuePage'
import { AnalyticsPage } from '@/pages/AnalyticsPage'
import { AlertCircle, RefreshCw } from 'lucide-react'

export function App() {
  const [activeTab, setActiveTab] = useState<TabType>('overview')
  const [summary, setSummary] = useState<StudioSummary | null>(null)
  const [decisions, setDecisions] = useState<DecisionRecord[]>([])
  const [graph, setGraph] = useState<ProvenanceGraphData | null>(null)
  const [pendingDrafts, setPendingDrafts] = useState<PendingDraft[]>([])
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null)

  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [networkError, setNetworkError] = useState<string | null>(null)
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState<boolean>(false)

  // Primary data fetcher
  const loadData = useCallback(async (isSilent = false) => {
    try {
      if (!isSilent) setIsLoading(true)
      const [sum, dec, gr, pend, an] = await Promise.all([
        api.getSummary().catch((e) => {
          console.error('getSummary error:', e)
          return null
        }),
        api.getDecisions().catch((e) => {
          console.error('getDecisions error:', e)
          return []
        }),
        api.getGraph().catch((e) => {
          console.error('getGraph error:', e)
          return null
        }),
        api.getPendingApprovals().catch((e) => {
          console.error('getPendingApprovals error:', e)
          return []
        }),
        api.getAnalytics().catch((e) => {
          console.error('getAnalytics error:', e)
          return null
        }),
      ])

      if (sum) setSummary(sum)
      if (dec) setDecisions(dec)
      if (gr) setGraph(gr)
      if (pend) setPendingDrafts(pend)
      if (an) setAnalytics(an)

      setNetworkError(null)
    } catch (err: any) {
      console.error('Data refresh error:', err)
      setNetworkError(err.message || 'Unable to connect to Doctus Studio backend')
    } finally {
      if (!isSilent) setIsLoading(false)
    }
  }, [])

  // Initial load + interval polling with page visibility check
  useEffect(() => {
    loadData(false)

    const interval = setInterval(() => {
      if (!document.hidden) {
        loadData(true)
      }
    }, 5000)

    return () => clearInterval(interval)
  }, [loadData])

  return (
    <div className="flex h-screen overflow-hidden bg-dark-950 text-slate-100 font-sans">
      <Toaster
        theme="dark"
        position="bottom-right"
        toastOptions={{
          style: {
            background: '#0c0e12',
            border: '1px solid #252b37',
            color: '#f8fafc',
          },
        }}
      />

      {/* Responsive Sidebar */}
      <Sidebar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        summary={summary}
        isMobileOpen={isMobileSidebarOpen}
        onCloseMobile={() => setIsMobileSidebarOpen(false)}
      />

      {/* Main Workspace Area */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        <Header
          summary={summary}
          onRefresh={() => loadData(true)}
          onToggleMobileSidebar={() => setIsMobileSidebarOpen(!isMobileSidebarOpen)}
        />

        {/* Network Error Banner if backend is unreachable */}
        {networkError && (
          <div className="bg-crimson-950/80 border-b border-crimson-700/60 px-6 py-2.5 flex items-center justify-between text-xs text-crimson-200">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-crimson-400 shrink-0" />
              <span>Backend Connection Alert: {networkError}</span>
            </div>
            <button
              onClick={() => loadData(false)}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-crimson-900 hover:bg-crimson-800 text-white font-semibold transition"
            >
              <RefreshCw className="w-3 h-3" />
              <span>Retry</span>
            </button>
          </div>
        )}

        {/* Scrollable tab content */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 md:p-8">
          {activeTab === 'overview' && (
            <OverviewPage
              summary={summary}
              decisions={decisions}
              graph={graph}
              onRefresh={() => loadData(true)}
              onNavigateTab={setActiveTab}
            />
          )}

          {activeTab === 'provenance' && (
            <LineagePage graph={graph} />
          )}

          {activeTab === 'countersign' && (
            <LegalQueuePage
              pendingDrafts={pendingDrafts}
              onRefresh={() => loadData(true)}
              onNavigateTab={(tab) => setActiveTab(tab as TabType)}
            />
          )}

          {activeTab === 'analytics' && (
            <AnalyticsPage analytics={analytics} summary={summary} />
          )}
        </main>
      </div>
    </div>
  )
}

export default App

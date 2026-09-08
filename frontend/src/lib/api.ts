import {
  StudioSummary,
  ProvenanceGraphData,
  DecisionRecord,
  PendingDraft,
  AnalyticsData,
  PreflightVerdict,
} from '@/types'

const API_BASE = ''
const request = (url: string, options?: RequestInit) => fetch(url, { ...options, signal: AbortSignal.timeout(15000) })

export const assetName = (id: string) => ({
  ast_hero_shot_v1: 'City at midnight', ast_music_bed_v1: 'Midnight ambient score',
  ast_talent_frame_v1: 'Lead character portrait', ast_composite_v1: 'The Last Echo · Festival cut',
  ast_video_shot_v1: 'The Last Echo · Motion study', ast_composite_demo: 'Hero shot with music',
  ast_veo_shot_demo: 'AI-generated city scene',
}[id] || id.replace(/^ast_/, '').replace(/_v\d+$/, '').replaceAll('_', ' '))
export const reasonLabel = (reason: string) => ({
  SCOPE_EXCEEDED: 'Usage not covered', UNTRUSTED_SIGNER: 'Unverified rights holder',
  MISSING_MANIFEST: 'Missing content credentials', WINDOW_EXPIRED: 'Permission expired',
  EXPIRED: 'Permission expired', MISSING_CLAIM: 'Permission missing',
}[reason] || reason?.toLowerCase().replaceAll('_', ' ') || 'Review required')
export function readableJson(value?: string | null) {
  if (!value) return 'No additional details recorded.'
  try { return JSON.stringify(JSON.parse(value), null, 2) } catch { return value }
}
export async function downloadCertificate() {
  const response = await request('/api/certificate/export')
  if (!response.ok) throw new Error('The report could not be generated. Please try again.')
  const blob = await response.blob()
  if (!blob.type.includes('text/html')) throw new Error('An unexpected report format was returned.')
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url; link.download = 'doctus_clearance_report.html'; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorMsg = `HTTP Error ${res.status}: ${res.statusText}`
    try {
      const errorJson = await res.json()
      if (errorJson.detail) errorMsg = errorJson.detail
      else if (errorJson.error) errorMsg = errorJson.error
    } catch {
      // ignore
    }
    throw new Error(errorMsg)
  }
  const json = await res.json()
  if (json.ok === false) {
    throw new Error(json.error || json.message || 'Operation failed')
  }
  return (json.data !== undefined ? json.data : json) as T
}

export const api = {
  async getSummary(): Promise<StudioSummary> {
    const res = await request(`${API_BASE}/api/summary`)
    return handleResponse<StudioSummary>(res)
  },

  async getGraph(): Promise<ProvenanceGraphData> {
    const res = await request(`${API_BASE}/api/graph`)
    return handleResponse<ProvenanceGraphData>(res)
  },

  async getDecisions(): Promise<DecisionRecord[]> {
    const res = await request(`${API_BASE}/api/decisions`)
    return handleResponse<DecisionRecord[]>(res)
  },

  async getPendingApprovals(): Promise<PendingDraft[]> {
    const res = await request(`${API_BASE}/api/countersign/pending`)
    return handleResponse<PendingDraft[]>(res)
  },

  async getAnalytics(): Promise<AnalyticsData> {
    const res = await request(`${API_BASE}/api/analytics`)
    return handleResponse<AnalyticsData>(res)
  },

  async runPreflight(params: {
    asset_id: string
    verb?: string
    channel?: string
    territory?: string
  }): Promise<PreflightVerdict> {
    const res = await request(`${API_BASE}/api/preflight`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        asset_id: params.asset_id,
        verb: params.verb || 'publish',
        channel: params.channel || null,
        territory: params.territory || null,
      }),
    })
    const data = await handleResponse<{ ok: boolean; verdict: PreflightVerdict }>(res)
    return data.verdict
  },

  async approveDraft(
    draft_id: string,
    approver: string = 'Elena Vance (Studio Legal Lead)'
  ): Promise<{ ok: boolean; claim_id: string; approver: string }> {
    const res = await request(`${API_BASE}/api/countersign/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ draft_id, approver }),
    })
    return handleResponse<{ ok: boolean; claim_id: string; approver: string }>(res)
  },

  async runDemoBeat(beat: number | null = null): Promise<any> {
    const res = await request(`${API_BASE}/api/demo/run_beat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ beat }),
    })
    return handleResponse<any>(res)
  },

  async resetDemo(): Promise<{ ok: boolean; message: string }> {
    const res = await request(`${API_BASE}/api/demo/reset`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
    return handleResponse<{ ok: boolean; message: string }>(res)
  },

  getCertificateDownloadUrl(): string {
    return `${API_BASE}/api/certificate/export`
  },
}

import {
  StudioSummary,
  ProvenanceGraphData,
  DecisionRecord,
  PendingDraft,
  AnalyticsData,
  PreflightVerdict,
} from '@/types'

const API_BASE = ''

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
    const res = await fetch(`${API_BASE}/api/summary`)
    return handleResponse<StudioSummary>(res)
  },

  async getGraph(): Promise<ProvenanceGraphData> {
    const res = await fetch(`${API_BASE}/api/graph`)
    return handleResponse<ProvenanceGraphData>(res)
  },

  async getDecisions(): Promise<DecisionRecord[]> {
    const res = await fetch(`${API_BASE}/api/decisions`)
    return handleResponse<DecisionRecord[]>(res)
  },

  async getPendingApprovals(): Promise<PendingDraft[]> {
    const res = await fetch(`${API_BASE}/api/countersign/pending`)
    return handleResponse<PendingDraft[]>(res)
  },

  async getAnalytics(): Promise<AnalyticsData> {
    const res = await fetch(`${API_BASE}/api/analytics`)
    return handleResponse<AnalyticsData>(res)
  },

  async runPreflight(params: {
    asset_id: string
    verb?: string
    channel?: string
    territory?: string
  }): Promise<PreflightVerdict> {
    const res = await fetch(`${API_BASE}/api/preflight`, {
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
    const res = await fetch(`${API_BASE}/api/countersign/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ draft_id, approver }),
    })
    return handleResponse<{ ok: boolean; claim_id: string; approver: string }>(res)
  },

  async runDemoBeat(beat: number | null = null): Promise<any> {
    const res = await fetch(`${API_BASE}/api/demo/run_beat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ beat }),
    })
    return handleResponse<any>(res)
  },

  async resetDemo(): Promise<{ ok: boolean; message: string }> {
    const res = await fetch(`${API_BASE}/api/demo/reset`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
    return handleResponse<{ ok: boolean; message: string }>(res)
  },

  getCertificateDownloadUrl(): string {
    return `${API_BASE}/api/certificate/export`
  },
}

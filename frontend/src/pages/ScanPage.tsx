import { useEffect, useRef, useState } from 'react'
import { AlertCircle, ArrowDownToLine, CheckCircle2, FileUp, Info, ScanLine, ShieldCheck, X } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'

interface ScanResult {
  filename: string; sha256: string; scanned_at: string; allowed: boolean
  reason: string; detail: string; next_step: string; channel: string; territory: string
  trust_policy: string; retention: string
  claims: { claim_id: string; kind: string; signer: string; trusted: boolean }[]
}
const channels: Record<string, string> = { social: 'Social media', festival: 'Film festival', trailer: 'Promotional trailer', theatrical: 'Theatrical release' }
const regions: Record<string, string> = { US: 'United States', EU: 'European Union', Global: 'Worldwide' }
const escapeHtml = (value: unknown) => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!))
function saveReport(r: ScanResult) {
  const html = `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Doctus asset scan report</title><style>body{font:15px/1.7 system-ui;color:#263c36;background:#f5f7f2;padding:24px}main{max-width:800px;margin:auto;background:white;padding:32px;border-top:4px solid #247a60}h1{font-size:28px}h2{font-size:19px}p,li{overflow-wrap:anywhere}.notice{padding:18px;background:#e9f3e5}::selection{color:#123c2c;background:#bce4d2}@media print{body{padding:0;background:white}main{padding:10px}}@media(max-width:500px){body,main{padding:12px}}</style><main><p>DOCTUS / ASSET SCAN</p><h1>${r.allowed ? 'Recorded permissions cover this use' : 'Clearance not confirmed'}</h1><p><strong>File:</strong> ${escapeHtml(r.filename)}<br><strong>Scanned:</strong> ${escapeHtml(r.scanned_at)}<br><strong>Use:</strong> ${escapeHtml(r.channel)} · ${escapeHtml(r.territory)}<br><strong>SHA-256:</strong> ${escapeHtml(r.sha256)}<br><strong>Result:</strong> ${escapeHtml(r.reason)}</p><h2>What we found</h2><p>${escapeHtml(r.detail)}</p><h2>Your next step</h2><p>${escapeHtml(r.next_step)}</p><h2>Rights records</h2><ul>${r.claims.map(c => `<li>${escapeHtml(c.kind)} · ${escapeHtml(c.signer)} · ${c.trusted ? 'Trusted under this policy' : 'Unverified signer'}<br>${escapeHtml(c.claim_id)}</li>`).join('') || '<li>No supported rights records found.</li>'}</ul><div class="notice"><strong>Scope and limitations</strong><p>${escapeHtml(r.trust_policy)}</p><p>Only this uploaded file was evaluated. External contracts, source ingredients, ownership, and visual similarity are not verified. This is not legal advice, an insurance certificate, or a malware scan.</p><p>${escapeHtml(r.retention)}</p></div></main></html>`
  const url = URL.createObjectURL(new Blob([html], { type: 'text/html' }))
  const a = document.createElement('a'); a.href = url; a.download = 'doctus_asset_scan_report.html'; a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function ScanPage() {
  const [file, setFile] = useState<File | null>(null)
  const [channel, setChannel] = useState('social')
  const [region, setRegion] = useState('US')
  const [consent, setConsent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [loadingSample, setLoadingSample] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState('')
  const [result, setResult] = useState<ScanResult | null>(null)
  const input = useRef<HTMLInputElement>(null)
  const xhr = useRef<XMLHttpRequest | null>(null)
  const mounted = useRef(true)
  const sample = useRef<AbortController | null>(null)
  const resultRef = useRef<HTMLElement>(null)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; xhr.current?.abort(); sample.current?.abort() } }, [])
  const selectFile = (next?: File) => {
    if (!next) return
    setResult(null); setError(''); setConsent(false)
    if (!/\.(jpe?g|png|webp|mp4)$/i.test(next.name)) { setFile(null); setError('Choose a JPG, PNG, WebP, or MP4 file.'); return }
    if (!next.size || next.size > 20 * 1024 * 1024) { setFile(null); setError(next.size ? 'Your file exceeds the 20 MB limit. Choose a smaller original file.' : 'This file is empty. Choose another file.'); return }
    setFile(next)
  }
  const loadSample = async (name: string, destination: string) => {
    setLoadingSample(true); setError('')
    const controller = new AbortController(); sample.current = controller
    try {
      const response = await fetch(`/media/${name}`, { signal: controller.signal })
      if (!response.ok) throw new Error()
      const blob = await response.blob()
      if (mounted.current) { selectFile(new File([blob], name, { type: blob.type })); setChannel(destination); setRegion('US') }
    } catch { if (mounted.current && !controller.signal.aborted) setError('The sample could not load. Choose your own file or try again.') }
    finally { if (mounted.current) setLoadingSample(false) }
  }
  const scan = () => {
    if (!file || busy || !consent) return
    setBusy(true); setProgress(0); setError(''); setResult(null)
    const request = new XMLHttpRequest(); xhr.current = request
    request.open('POST', `/api/assets/scan?${new URLSearchParams({ filename: file.name, channel, territory: region })}`)
    request.setRequestHeader('Content-Type', 'application/octet-stream'); request.timeout = 70000
    request.upload.onprogress = e => { if (mounted.current && e.lengthComputable) setProgress(Math.round(e.loaded / e.total * 100)) }
    request.upload.onload = () => { if (mounted.current) setProgress(100) }
    request.onload = () => {
      if (!mounted.current) return
      try {
        const response = JSON.parse(request.responseText)
        if (request.status < 200 || request.status >= 300 || !response.ok) throw new Error(typeof response.detail === 'string' ? response.detail : 'This scan could not be completed. Please try again.')
        setResult(response.data)
        setTimeout(() => { resultRef.current?.focus(); resultRef.current?.scrollIntoView({ block: 'nearest' }) }, 0)
      } catch (e) { setError(e instanceof Error ? e.message : 'No clearance could be confirmed. Please try again.') }
    }
    request.onerror = () => { if (mounted.current) setError('Connection interrupted. Try again. No clearance is confirmed.') }
    request.ontimeout = () => { if (mounted.current) setError('The scan timed out. Try a smaller original file.') }
    request.onabort = () => { if (mounted.current) setError('Scan canceled. No clearance result was saved.') }
    request.onloadend = () => { if (mounted.current) setBusy(false); xhr.current = null }
    request.send(file)
  }
  return <div className="page-stack scan-page">
    <div className="page-heading"><div><span className="eyebrow">YOUR ASSET. A CLEARER NEXT STEP.</span><h1>Upload it. Understand its rights.</h1><p>Check embedded credentials and permissions before you publish.</p></div><Badge variant="info" size="md"><ScanLine size={16} />Isolated file scan</Badge></div>
    <div className="scan-layout"><section className="card scan-form"><div className="scan-step"><span>01</span><div><h2>Choose your asset</h2><p>One original image or video, up to 20 MB.</p></div></div>
      <input ref={input} type="file" className="sr-only" aria-label="Choose asset file" accept=".jpg,.jpeg,.png,.webp,.mp4" disabled={busy || loadingSample} onChange={e => { selectFile(e.target.files?.[0]); e.target.value = '' }} />
      <div className={`upload-zone ${dragging ? 'drag-active' : ''}`} onDragOver={e => { e.preventDefault(); if (!busy && !loadingSample) setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={e => { e.preventDefault(); setDragging(false); if (busy || loadingSample) return; if (e.dataTransfer.files.length !== 1) { setError('Choose one file at a time.'); return } selectFile(e.dataTransfer.files[0]) }}>
        <span className="upload-symbol"><FileUp size={32} /></span>{file ? <><div className="upload-selected"><div><strong>{file.name}</strong><p>{(file.size / 1024 / 1024).toFixed(2)} MB · Ready to scan</p></div><button className="icon-button" aria-label="Remove selected file" disabled={busy || loadingSample} onClick={() => { setFile(null); setResult(null); setConsent(false); setError('') }}><X size={18} /></button></div><Button variant="secondary" disabled={busy || loadingSample} onClick={() => input.current?.click()}>Choose another file</Button></> : <><h3>Drop your file here</h3><p>JPG, PNG, WebP, or MP4</p><Button variant="secondary" disabled={loadingSample} onClick={() => input.current?.click()}>Browse files</Button></>}<small>Nothing is uploaded until you select “Upload & scan”.</small>
      </div>
      <form onSubmit={e => { e.preventDefault(); scan() }}><fieldset className="check-fields" disabled={busy || loadingSample}><div className="scan-step"><span>02</span><div><h2>Tell us how you’ll use it</h2><p>Permissions can differ by destination and region.</p></div></div><div className="form-row"><label htmlFor="scan-channel">Destination<select id="scan-channel" value={channel} onChange={e => { setChannel(e.target.value); setResult(null) }}>{Object.entries(channels).map(([id,label]) => <option key={id} value={id}>{label}</option>)}</select></label><label htmlFor="scan-region">Region<select id="scan-region" value={region} onChange={e => { setRegion(e.target.value); setResult(null) }}>{Object.entries(regions).map(([id,label]) => <option key={id} value={id}>{label}</option>)}</select></label></div><label className="checkbox-label"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} /><span>I’m permitted to upload this file. It will be processed on this server and deleted after scanning. I won’t upload confidential material to this unauthenticated preview.</span></label><Button type="submit" className="full-width" disabled={!file || !consent} isLoading={busy}><ScanLine size={18} />{busy ? progress < 100 ? `Uploading… ${progress}%` : 'Scanning credentials…' : 'Upload & scan'}</Button></fieldset></form>
      {busy && <div className="scan-progress" role="status"><progress value={progress} max={100} aria-label="Upload progress" /><p>{progress < 100 ? 'Uploading your file…' : 'Checking signatures and permissions. This may take up to 30 seconds.'}</p><Button variant="ghost" size="sm" onClick={() => xhr.current?.abort()}>Cancel scan</Button></div>}{error && <div className="result result-error" role="alert"><AlertCircle size={20} /><p>{error}</p></div>}
    </section><aside className="scan-sidebar"><div className="card padded"><ShieldCheck size={27} /><h2>What a scan can tell you</h2><ul className="scan-checklist">{['Whether readable embedded credentials exist','Which supported rights records they contain','Whether they cover your requested use'].map(t => <li key={t}><CheckCircle2 size={17} />{t}</li>)}</ul><div className="scan-limit"><Info size={18} /><p>This checks C2PA credentials and Doctus rights assertions—not pixels. It cannot prove ownership, detect plagiarism, inspect external contracts, or replace legal review.</p></div></div><div className="card padded scan-samples"><h2>No file handy?</h2><p>Load a signed sample, then try the same upload flow.</p><button disabled={busy || loadingSample} onClick={() => loadSample('ast_talent_frame_v1.jpg','social')}><FileUp size={20} /><span><strong>Character portrait</strong><small>Try social-media permissions</small></span></button><button disabled={busy || loadingSample} onClick={() => loadSample('ast_music_bed_v1.jpg','trailer')}><FileUp size={20} /><span><strong>Music rights sample</strong><small>Try a restricted trailer use</small></span></button>{loadingSample && <p role="status">Loading sample…</p>}</div><div className="notice"><Info size={20} /><div><strong>Your upload stays separate</strong><p>Files are scanned in isolation, not added to the shared sample library. They are deleted afterward. Download your report before leaving this page.</p></div></div></aside></div>
    {result && <section ref={resultRef} tabIndex={-1} className="card scan-result" aria-label="Asset scan result"><div className="scan-result-heading">{result.allowed ? <ShieldCheck size={35} /> : <AlertCircle size={35} />}<div><span className="eyebrow">SCAN COMPLETE</span><h2>{result.allowed ? 'Recorded permissions cover this use.' : 'Clearance could not be confirmed.'}</h2><p>{result.filename} · {channels[result.channel]} · {regions[result.territory]}</p></div><Button variant="secondary" onClick={() => saveReport(result)}><ArrowDownToLine size={16} />Save scan report</Button></div><div className="scan-result-grid"><div><h3>What we found</h3><p>{result.detail}</p><h3>Your next step</h3><p>{result.next_step}</p></div><div><h3>Embedded rights records</h3>{result.claims.length ? result.claims.map(c => <div className="scan-claim" key={c.claim_id}><strong>{c.kind.replaceAll('_',' ')}</strong><span>{c.signer}</span><Badge variant={c.trusted ? 'success' : 'warning'}>{c.trusted ? 'Trusted under this policy' : 'Unverified signer'}</Badge></div>) : <p>No supported rights records were available.</p>}</div></div><details><summary>Technical details & trust policy</summary><p>Scanned: {new Date(result.scanned_at).toLocaleString()}</p><p>Result: {result.reason}</p><p>SHA-256: <code>{result.sha256}</code></p><p>{result.trust_policy}</p></details><p className="scan-disclaimer">This result applies only to this file and requested use. It is not legal advice, insurance, or a malware scan. Changing the destination requires a new scan.</p></section>}
  </div>
}

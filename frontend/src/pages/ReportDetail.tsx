import { useState, useEffect, useMemo } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { apiFetch, apiFetchFile, ApiError } from '../api/client'
import type { Report, UploadResult, AnalysisResult, CustomerResult } from '../types/report'

const SEGMENT_ORDER: Record<string, number> = {
  'Champions': 1,
  'Loyal Customers': 2,
  'Potential Loyalists': 3,
  'At Risk': 4,
  'Hibernating': 5,
  'Others': 6,
}

const COLUMNS: Array<{ key: keyof CustomerResult; label: string }> = [
  { key: 'customer_id', label: 'Customer ID' },
  { key: 'segment', label: 'Segment' },
  { key: 'r_score', label: 'R' },
  { key: 'f_score', label: 'F' },
  { key: 'm_score', label: 'M' },
  { key: 'recency_days', label: 'Recency (days)' },
  { key: 'frequency', label: 'Frequency' },
  { key: 'monetary', label: 'Monetary ($)' },
]

// 2s interval × 60 attempts ≈ 2 minutes — well past the 30s the UI promises.
const MAX_POLL_ATTEMPTS = 60
const MAX_CONSECUTIVE_POLL_FAILURES = 3

export default function ReportDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [report, setReport] = useState<Report | null>(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deleteInFlight, setDeleteInFlight] = useState(false)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle')
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadEventsAdded, setUploadEventsAdded] = useState<number | null>(null)
  const [sampleCount, setSampleCount] = useState(150)
  const [sampleStatus, setSampleStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [sampleError, setSampleError] = useState<string | null>(null)
  const [sampleEventsAdded, setSampleEventsAdded] = useState<number | null>(null)
  const [analysisStatus, setAnalysisStatus] = useState<'idle' | 'triggering' | 'error'>('idle')
  const [analysisError, setAnalysisError] = useState<string | null>(null)
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null)
  const [resultsError, setResultsError] = useState<string | null>(null)
  const [pollError, setPollError] = useState<string | null>(null)
  const [pollGeneration, setPollGeneration] = useState(0)
  const [sortKey, setSortKey] = useState<keyof CustomerResult>('segment')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')

  useEffect(() => {
    if (!id) return
    let cancelled = false
    // Reset per-report analysis state so a route-param change never shows
    // the previous report's results (the results effect guards on !== null).
    setAnalysisResult(null)
    setResultsError(null)
    setPollError(null)
    apiFetch(`/api/reports/${id}`)
      .then((data) => {
        if (!cancelled) setReport(data as Report)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 404) {
          setNotFound(true)
        } else {
          setError('Failed to load report')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [id])

  // Polling: while the report is analyzing, re-fetch every 2 seconds.
  // Capped at MAX_POLL_ATTEMPTS; stops early after consecutive failures.
  // pollGeneration lets the "Keep waiting" button restart an expired loop.
  useEffect(() => {
    if (report?.status !== 'analyzing') return
    setPollError(null)
    let cancelled = false
    let attempts = 0
    let consecutiveFailures = 0
    const interval = setInterval(() => {
      if (!id) return
      attempts += 1
      if (attempts > MAX_POLL_ATTEMPTS) {
        clearInterval(interval)
        setPollError('Analysis is taking longer than expected. It may still be running on the server.')
        return
      }
      apiFetch(`/api/reports/${id}`)
        .then((data) => {
          if (cancelled) return
          consecutiveFailures = 0
          setReport(data as Report)
        })
        .catch((err: unknown) => {
          if (cancelled) return
          consecutiveFailures += 1
          if (consecutiveFailures >= MAX_CONSECUTIVE_POLL_FAILURES) {
            clearInterval(interval)
            setPollError(err instanceof ApiError ? err.detail : 'Failed to check analysis status.')
          }
        })
    }, 2000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [report?.status, id, pollGeneration])

  // When status reaches 'completed' and we have no results yet, fetch them.
  useEffect(() => {
    if (report?.status !== 'completed' || analysisResult !== null || !id) return
    loadResults()
  // analyzed_at changes on every completed run, so a re-run re-fires this
  // even when status stays 'completed' throughout. analysisResult intentionally
  // omitted: adding it would refetch stale results mid-re-run.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [report?.status, report?.analyzed_at, id])

  async function handleUpload() {
    if (!uploadFile || !id) return
    setUploadStatus('uploading')
    setUploadError(null)
    setUploadEventsAdded(null)

    if (uploadFile.name.toLowerCase().endsWith('.csv')) {
      const text = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(reader.result as string)
        reader.onerror = () => reject(reader.error)
        reader.readAsText(uploadFile)
      })
      const lineCount = (text.match(/\n/g) ?? []).length
      if (lineCount > 200_000) {
        setUploadStatus('error')
        setUploadError(
          `File contains too many rows (estimated ${lineCount.toLocaleString()}). Maximum is 200,000.`,
        )
        return
      }
    }

    try {
      const formData = new FormData()
      formData.append('file', uploadFile)
      const result = (await apiFetchFile(`/api/reports/${id}/events/upload`, formData)) as UploadResult
      setUploadStatus('success')
      setUploadEventsAdded(result.events_added)
      const updated = (await apiFetch(`/api/reports/${id}`)) as Report
      setReport(updated)
    } catch (err: unknown) {
      setUploadStatus('error')
      if (err instanceof ApiError) {
        setUploadError(err.detail)
      } else {
        setUploadError('Upload failed. Please try again.')
      }
    }
  }

  async function handleGenerateSample() {
    if (!id) return
    setSampleStatus('loading')
    setSampleError(null)
    setSampleEventsAdded(null)
    try {
      const result = (await apiFetch(`/api/reports/${id}/events/sample`, {
        method: 'POST',
        body: JSON.stringify({ count: sampleCount }),
      })) as UploadResult
      setSampleStatus('success')
      setSampleEventsAdded(result.events_added)
      const updated = (await apiFetch(`/api/reports/${id}`)) as Report
      setReport(updated)
    } catch (err: unknown) {
      setSampleStatus('error')
      if (err instanceof ApiError) {
        setSampleError(err.detail)
      } else {
        setSampleError('Sample generation failed. Please try again.')
      }
    }
  }

  async function handleDelete() {
    if (!id || deleteInFlight) return
    setDeleteInFlight(true)
    try {
      await apiFetch(`/api/reports/${id}`, { method: 'DELETE' })
      navigate('/')
    } catch {
      setDeleteInFlight(false)
      setShowDeleteModal(false)
    }
  }

  function loadResults() {
    if (!id) return
    setResultsError(null)
    apiFetch(`/api/reports/${id}/analysis/results`)
      .then((data) => setAnalysisResult(data as AnalysisResult))
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setResultsError(err.detail)
        } else {
          setResultsError('Failed to load analysis results.')
        }
      })
  }

  async function handleRunAnalysis() {
    if (!id) return
    setAnalysisStatus('triggering')
    setAnalysisError(null)
    try {
      await apiFetch(`/api/reports/${id}/analysis/run`, { method: 'POST' })
      setAnalysisStatus('idle')
      const updated = (await apiFetch(`/api/reports/${id}`)) as Report
      setReport(updated)
    } catch (err: unknown) {
      setAnalysisStatus('error')
      if (err instanceof ApiError) {
        setAnalysisError(err.detail)
      } else {
        setAnalysisError('Failed to start analysis. Please try again.')
      }
    }
  }

  function handleSort(key: keyof CustomerResult) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  const sortedCustomers: CustomerResult[] = useMemo(() => {
    if (!analysisResult) return []
    return [...analysisResult.customers].sort((a, b) => {
      let cmp: number
      if (sortKey === 'segment') {
        cmp = (SEGMENT_ORDER[a.segment] ?? 99) - (SEGMENT_ORDER[b.segment] ?? 99)
        if (cmp === 0) cmp = a.customer_id.localeCompare(b.customer_id)
      } else {
        const valA = a[sortKey]
        const valB = b[sortKey]
        if (typeof valA === 'string' && typeof valB === 'string') {
          cmp = valA.localeCompare(valB)
        } else {
          cmp = (valA as number) - (valB as number)
        }
      }
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [analysisResult, sortKey, sortDir])

  if (loading) return <p>Loading…</p>

  if (notFound) {
    return (
      <div>
        <p>Report not found.</p>
        <Link to="/">← Back to reports</Link>
      </div>
    )
  }

  if (error) return <p style={{ color: 'red' }}>{error}</p>
  if (!report) return null

  return (
    <div>
      <Link to="/">← Back to reports</Link>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginTop: 16 }}>
        <h1 style={{ margin: 0 }}>{report.name}</h1>
        <button type="button" onClick={() => setShowDeleteModal(true)}>
          Delete
        </button>
      </div>

      {report.description && <p>{report.description}</p>}

      <p style={{ color: '#666', fontSize: 14 }}>
        Status: <strong>{report.status}</strong> · {report.event_count} events
      </p>

      {report.status === 'created' && (
        <div style={{ marginTop: 24 }}>
          <h3 style={{ margin: '0 0 8px' }}>Add Events</h3>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              type="file"
              accept=".csv,.json"
              onChange={(e) => {
                setUploadFile(e.target.files?.[0] ?? null)
                setUploadStatus('idle')
                setUploadError(null)
                setUploadEventsAdded(null)
              }}
            />
            <button
              type="button"
              onClick={handleUpload}
              disabled={uploadStatus === 'uploading' || uploadFile === null}
            >
              {uploadStatus === 'uploading' ? 'Uploading…' : 'Upload'}
            </button>
          </div>
          {uploadStatus === 'success' && uploadEventsAdded !== null && (
            <p style={{ color: 'green', marginTop: 8 }}>
              Successfully uploaded {uploadEventsAdded.toLocaleString()} events.
            </p>
          )}
          {uploadStatus === 'error' && uploadError && (
            <p style={{ color: 'red', marginTop: 8 }}>{uploadError}</p>
          )}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 16 }}>
            <label>
              Sample count:
              <input
                type="number"
                min={1}
                max={250_000}
                value={sampleCount}
                onChange={(e) => {
                  const parsed = Number(e.target.value)
                  if (!Number.isNaN(parsed) && parsed >= 1) setSampleCount(parsed)
                  setSampleStatus('idle')
                  setSampleError(null)
                }}
                style={{ marginLeft: 8, width: 100 }}
              />
            </label>
            <button
              type="button"
              onClick={handleGenerateSample}
              disabled={sampleStatus === 'loading'}
            >
              {sampleStatus === 'loading' ? 'Generating…' : 'Generate Sample'}
            </button>
          </div>
          {sampleStatus === 'success' && sampleEventsAdded !== null && (
            <p style={{ color: 'green', marginTop: 8 }}>
              Successfully generated {sampleEventsAdded.toLocaleString()} sample events.
            </p>
          )}
          {sampleStatus === 'error' && sampleError && (
            <p style={{ color: 'red', marginTop: 8 }}>{sampleError}</p>
          )}
          <button
            type="button"
            onClick={() => { void handleRunAnalysis() }}
            disabled={analysisStatus === 'triggering' || report.event_count === 0}
            title={report.event_count === 0 ? 'Add events first to run analysis' : undefined}
            style={{ marginTop: 16 }}
          >
            {analysisStatus === 'triggering' ? 'Starting…' : 'Run Analysis'}
          </button>
          {analysisStatus === 'error' && analysisError && (
            <p style={{ color: 'red', marginTop: 8 }}>{analysisError}</p>
          )}
        </div>
      )}

      {report.status === 'analyzing' && (
        <div style={{ marginTop: 24 }}>
          {pollError !== null ? (
            <div>
              <p style={{ color: 'red' }}>{pollError}</p>
              <button type="button" onClick={() => setPollGeneration((g) => g + 1)}>
                Keep waiting
              </button>
            </div>
          ) : (
            <p className="analyzing-pulse">Analyzing… this may take up to 30 seconds.</p>
          )}
        </div>
      )}

      {report.status === 'failed' && (
        <div style={{ marginTop: 24 }}>
          <p style={{ color: 'red' }}>Analysis failed. Please try again.</p>
          <button
            type="button"
            onClick={() => { void handleRunAnalysis() }}
            disabled={analysisStatus === 'triggering'}
          >
            {analysisStatus === 'triggering' ? 'Starting…' : 'Retry'}
          </button>
        </div>
      )}

      {report.status === 'completed' && (
        <div style={{ marginTop: 24 }}>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 16 }}>
            <span><strong>Total Events:</strong> {report.event_count.toLocaleString()}</span>
            {analysisResult && (
              <>
                <span><strong>Unique Customers:</strong> {analysisResult.unique_customers.toLocaleString()}</span>
                {Object.entries(analysisResult.segment_counts)
                  .sort(([a], [b]) => (SEGMENT_ORDER[a] ?? 99) - (SEGMENT_ORDER[b] ?? 99))
                  .map(([seg, count]) => (
                    <span key={seg}><strong>{seg}:</strong> {count}</span>
                  ))}
              </>
            )}
          </div>
          <button
            type="button"
            onClick={() => { setAnalysisResult(null); void handleRunAnalysis() }}
            disabled={analysisStatus === 'triggering'}
            style={{ marginBottom: 16 }}
          >
            {analysisStatus === 'triggering' ? 'Starting…' : 'Re-run Analysis'}
          </button>
          {analysisResult === null ? (
            resultsError !== null ? (
              <div>
                <p style={{ color: 'red' }}>{resultsError}</p>
                <button type="button" onClick={loadResults}>Retry</button>
              </div>
            ) : (
              <p>Loading results…</p>
            )
          ) : (
            <table style={{ borderCollapse: 'collapse', width: '100%' }}>
              <thead>
                <tr>
                  {COLUMNS.map(({ key, label }) => (
                    <th
                      key={key}
                      onClick={() => handleSort(key)}
                      style={{
                        cursor: 'pointer',
                        padding: '8px',
                        textAlign: 'left',
                        borderBottom: '2px solid #ccc',
                        userSelect: 'none',
                      }}
                    >
                      {label} {sortKey === key ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedCustomers.map((row) => (
                  <tr key={row.customer_id}>
                    {COLUMNS.map(({ key }) => (
                      <td key={key} style={{ padding: '6px 8px' }}>
                        {key === 'monetary' ? `$${row.monetary.toFixed(2)}` : row[key]}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {showDeleteModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
          }}
        >
          <div style={{ background: '#fff', padding: 24, borderRadius: 8, maxWidth: 400, width: '100%' }}>
            <p>Delete "{report.name}"? This cannot be undone.</p>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button type="button" onClick={() => setShowDeleteModal(false)}>
                Cancel
              </button>
              <button type="button" onClick={handleDelete} disabled={deleteInFlight}>
                {deleteInFlight ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

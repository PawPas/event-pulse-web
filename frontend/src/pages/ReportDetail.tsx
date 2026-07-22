import { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { apiFetch, apiFetchFile, ApiError } from '../api/client'
import type { Report, UploadResult } from '../types/report'

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

  useEffect(() => {
    if (!id) return
    apiFetch(`/api/reports/${id}`)
      .then((data) => setReport(data as Report))
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 404) {
          setNotFound(true)
        } else {
          setError('Failed to load report')
        }
      })
      .finally(() => setLoading(false))
  }, [id])

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
            disabled={report.event_count === 0}
            title={report.event_count === 0 ? 'Add events first to run analysis' : undefined}
            style={{ marginTop: 16 }}
          >
            Run Analysis
          </button>
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

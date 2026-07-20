import { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { apiFetch, ApiError } from '../api/client'
import type { Report } from '../types/report'

export default function ReportDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [report, setReport] = useState<Report | null>(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deleteInFlight, setDeleteInFlight] = useState(false)

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
        <button
          type="button"
          disabled
          title="Add events first to run analysis"
          style={{ marginTop: 16 }}
        >
          Run Analysis
        </button>
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

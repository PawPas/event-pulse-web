import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch, ApiError } from '../api/client'
import type { Report } from '../types/report'

export default function ReportList() {
  const [reports, setReports] = useState<Report[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [creating, setCreating] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [deleteInFlight, setDeleteInFlight] = useState(false)

  useEffect(() => {
    apiFetch('/api/reports/')
      .then((data) => setReports(data as Report[]))
      .catch((err: unknown) => setError(err instanceof ApiError ? err.detail : 'Failed to load reports'))
      .finally(() => setLoading(false))
  }, [])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (creating) return
    setFormError(null)
    setCreating(true)
    try {
      const report = await apiFetch('/api/reports/', {
        method: 'POST',
        body: JSON.stringify({ name, description: description || null }),
      }) as Report
      setReports((prev) => [report, ...prev])
      setShowForm(false)
      setName('')
      setDescription('')
    } catch (err: unknown) {
      setFormError(err instanceof ApiError ? err.detail : 'Failed to create report')
    } finally {
      setCreating(false)
    }
  }

  async function handleDelete() {
    if (!deletingId || deleteInFlight) return
    setDeleteInFlight(true)
    try {
      await apiFetch(`/api/reports/${deletingId}`, { method: 'DELETE' })
      setReports((prev) => prev.filter((r) => r.id !== deletingId))
      setDeletingId(null)
    } catch {
      setDeletingId(null)
    } finally {
      setDeleteInFlight(false)
    }
  }

  const deletingReport = reports.find((r) => r.id === deletingId)

  if (loading) return <p>Loading…</p>
  if (error) return <p style={{ color: 'red' }}>{error}</p>

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h1 style={{ margin: 0 }}>Reports</h1>
        <button
          type="button"
          onClick={() => { setShowForm((s) => !s); setFormError(null) }}
        >
          {showForm ? 'Cancel' : 'Create New Report'}
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={handleCreate}
          style={{ border: '1px solid #eee', padding: 16, marginBottom: 16, borderRadius: 4 }}
        >
          <div style={{ marginBottom: 12 }}>
            <label>
              Name
              <br />
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                style={{ width: '100%', marginTop: 4 }}
              />
            </label>
          </div>
          <div style={{ marginBottom: 12 }}>
            <label>
              Description (optional)
              <br />
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                style={{ width: '100%', marginTop: 4 }}
              />
            </label>
          </div>
          {formError && <p style={{ color: 'red' }}>{formError}</p>}
          <div style={{ display: 'flex', gap: 8 }}>
            <button type="submit" disabled={creating}>
              {creating ? 'Creating…' : 'Create'}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowForm(false)
                setFormError(null)
                setName('')
                setDescription('')
              }}
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {reports.length === 0 ? (
        <p>No reports yet. Create your first one above.</p>
      ) : (
        <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
          {reports.map((report) => (
            <li
              key={report.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px 0',
                borderBottom: '1px solid #eee',
              }}
            >
              <div>
                <Link to={`/reports/${report.id}`} style={{ fontWeight: 500 }}>
                  {report.name}
                </Link>
                <span style={{ marginLeft: 8, fontSize: 12, color: '#888' }}>
                  {new Date(report.created_at).toLocaleDateString()} · {report.event_count} events
                </span>
              </div>
              <button type="button" onClick={() => setDeletingId(report.id)}>
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}

      {deletingId && (
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
            <p>Delete "{deletingReport?.name}"? This cannot be undone.</p>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button type="button" onClick={() => setDeletingId(null)}>
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

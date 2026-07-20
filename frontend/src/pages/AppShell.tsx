import { Outlet, useNavigate, Link } from 'react-router-dom'
import { useAppDispatch } from '../hooks/useAppDispatch'
import { useAppSelector } from '../hooks/useAppSelector'
import { logout } from '../store/authSlice'
import { apiFetch } from '../api/client'

export default function AppShell() {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const email = useAppSelector((state) => state.auth.user?.email)

  async function handleLogout() {
    dispatch(logout())
    try {
      await apiFetch('/api/auth/logout', { method: 'POST' })
    } catch {
      // token already cleared; ignore network errors
    }
    navigate('/login')
  }

  return (
    <>
      <nav style={{ display: 'flex', justifyContent: 'space-between', padding: '12px 24px', borderBottom: '1px solid #eee' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <Link to="/" style={{ fontWeight: 600, textDecoration: 'none' }}>EventPulse</Link>
          <span style={{ color: '#888' }}>{email}</span>
        </div>
        <button type="button" onClick={handleLogout}>Logout</button>
      </nav>
      <main style={{ padding: 24 }}>
        <Outlet />
      </main>
    </>
  )
}

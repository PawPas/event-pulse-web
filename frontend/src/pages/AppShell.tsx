import { Outlet, useNavigate } from 'react-router-dom'
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
        <span>{email}</span>
        <button type="button" onClick={handleLogout}>Logout</button>
      </nav>
      <main style={{ padding: 24 }}>
        <Outlet />
      </main>
    </>
  )
}

import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAppDispatch } from '../hooks/useAppDispatch'
import { loginSuccess } from '../store/authSlice'
import { apiFetch, ApiError } from '../api/client'

export default function Register() {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (loading) return
    setError(null)
    setLoading(true)
    try {
      const data = await apiFetch('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      }) as { access_token: string; user: { id: string; email: string } }
      dispatch(loginSuccess({ token: data.access_token, user: data.user }))
      navigate('/')
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 409) {
        setError('This email is already registered')
      } else {
        setError(err instanceof ApiError ? err.detail : 'Registration failed')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 360, margin: '80px auto', padding: '0 16px' }}>
      <h1>Create account</h1>
      <form onSubmit={handleSubmit}>
        <div>
          <label>Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            style={{ display: 'block', width: '100%', marginBottom: 12 }}
          />
        </div>
        <div>
          <label>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            style={{ display: 'block', width: '100%', marginBottom: 12 }}
          />
        </div>
        <button type="submit" disabled={loading}>{loading ? 'Creating account…' : 'Create account'}</button>
        {error && <p style={{ color: 'red' }}>{error}</p>}
      </form>
      <p>Already have an account? <Link to="/login">Sign in</Link></p>
    </div>
  )
}

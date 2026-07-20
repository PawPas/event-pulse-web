import { useAppSelector } from '../hooks/useAppSelector'

export default function Dashboard() {
  const email = useAppSelector((state) => state.auth.user?.email)

  return (
    <div>
      <h1>Welcome, {email}</h1>
      <p>Your dashboard will appear here.</p>
    </div>
  )
}

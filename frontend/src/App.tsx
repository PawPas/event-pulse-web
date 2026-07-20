import { Routes, Route } from 'react-router-dom'
import Login from './pages/Login'
import Register from './pages/Register'
import AppShell from './pages/AppShell'
import ReportList from './pages/ReportList'
import ReportDetail from './pages/ReportDetail'
import ProtectedRoute from './components/ProtectedRoute'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route index element={<ReportList />} />
        <Route path="reports/:id" element={<ReportDetail />} />
      </Route>
    </Routes>
  )
}

export default App

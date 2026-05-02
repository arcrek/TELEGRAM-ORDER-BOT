import { useEffect, type ReactNode } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { ThemeProvider } from './contexts/ThemeContext'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { ToastProvider } from './shared/components/Toast'
import { ConfirmDialogProvider } from './shared/components/ConfirmDialog'
import { Spinner } from './shared/components/Spinner'
import { setUnauthorizedHandler } from './shared/lib/api'
import { LoginPage } from './pages/LoginPage'
import { AppShell } from './app/layouts/AppShell'
import { StatisticsPage } from './pages/StatisticsPage'
import { ProductsPage } from './pages/ProductsPage'
import { OrdersPage } from './pages/OrdersPage'
import { ProductUploadPage } from './pages/ProductUploadPage'
import { PreUploadedPage } from './pages/PreUploadedPage'
import { VariationsPage } from './pages/VariationsPage'
import { BonusSummaryPage } from './pages/BonusSummaryPage'
import { SuppliersPage } from './pages/SuppliersPage'
import { NotificationsPage } from './pages/NotificationsPage'
import { IotdPage } from './pages/IotdPage'
import { BotUiSettingsPage } from './pages/BotUiSettingsPage'

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()
  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
        <Spinner size="lg" />
      </div>
    )
  }
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

function ApiBindings() {
  const navigate = useNavigate()
  const { logout } = useAuth()
  useEffect(() => {
    setUnauthorizedHandler(() => {
      logout()
      navigate('/login', { replace: true })
    })
    return () => setUnauthorizedHandler(() => {})
  }, [logout, navigate])
  return null
}

export function AppRoutes() {
  return (
    <>
      <ApiBindings />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <AppShell />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/statistics" replace />} />
          <Route path="statistics" element={<StatisticsPage />} />
          <Route path="products" element={<ProductsPage />} />
          <Route path="orders" element={<OrdersPage />} />
          <Route path="product-upload" element={<ProductUploadPage />} />
          <Route path="pre-uploaded" element={<PreUploadedPage />} />
          <Route path="variations" element={<VariationsPage />} />
          <Route path="bonus-summary" element={<BonusSummaryPage />} />
          <Route path="suppliers" element={<SuppliersPage />} />
          <Route path="notifications" element={<NotificationsPage />} />
          <Route path="bot-ui-settings" element={<BotUiSettingsPage />} />
          <Route path="iotd" element={<IotdPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}

export function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <ConfirmDialogProvider>
          <AuthProvider>
            <BrowserRouter>
              <AppRoutes />
            </BrowserRouter>
          </AuthProvider>
        </ConfirmDialogProvider>
      </ToastProvider>
    </ThemeProvider>
  )
}

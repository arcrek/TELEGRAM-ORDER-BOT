/**
 * Main App component with routing.
 */
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ThemeProvider } from './contexts/ThemeContext'
import { AuthProvider } from './contexts/AuthContext'
import { LoginPage } from './pages/LoginPage'
import { DashboardLayout } from './layouts/DashboardLayout'
import { StatisticsPage } from './pages/StatisticsPage'
import { ProductsPage } from './pages/ProductsPage'
import { OrdersPage } from './pages/OrdersPage'
import { ProductUploadPage } from './pages/ProductUploadPage'
import { PreUploadedPage } from './pages/PreUploadedPage'
import { VariationsPage } from './pages/VariationsPage'
import { SuppliersPage } from './pages/SuppliersPage'
import { NotificationsPage } from './pages/NotificationsPage'
import { ProtectedRoute } from './components/ProtectedRoute'
import './App.css'

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <DashboardLayout />
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
        <Route path="suppliers" element={<SuppliersPage />} />
        <Route path="notifications" element={<NotificationsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  )
}


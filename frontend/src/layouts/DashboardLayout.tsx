/**
 * Dashboard layout with navigation.
 */
import { useState, useEffect } from 'react'
import { Outlet, Link, useLocation } from 'react-router-dom'
// Users icon removed - supplier functionality disabled
import { Moon, Sun, BarChart3, Package, ShoppingCart, LogOut, Upload, Box, Layers, Bell, Sparkles, Menu, X, MessageSquare } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import { Button } from '../components/Button'
import { LanguageSelector } from '../components/LanguageSelector'
import './DashboardLayout.css'

export function DashboardLayout() {
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const { t } = useTranslation()
  const location = useLocation()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  // Close menu when route changes
  useEffect(() => {
    setMobileMenuOpen(false)
  }, [location.pathname])

  // Close menu when clicking outside (on overlay)
  const handleOverlayClick = () => {
    setMobileMenuOpen(false)
  }

  const navItems = [
    { path: '/statistics', label: t('navigation.statistics'), icon: BarChart3, key: 'statistics' },
    { path: '/products', label: t('navigation.products'), icon: Package, key: 'products' },
    { path: '/variations', label: t('navigation.variations'), icon: Layers, key: 'variations' },
    { path: '/orders', label: t('navigation.orders'), icon: ShoppingCart, key: 'orders' },
    { path: '/bonus-summary', label: t('navigation.bonusSummary'), icon: Sparkles, key: 'bonusSummary' },
    // Supplier functionality disabled
    // { path: '/suppliers', label: t('navigation.suppliers'), icon: Users, key: 'suppliers' },
    { path: '/notifications', label: t('navigation.notifications'), icon: Bell, key: 'notifications' },
    { path: '/bot-ui-settings', label: t('navigation.botUiSettings'), icon: MessageSquare, key: 'botUiSettings' },
    { path: '/product-upload', label: t('navigation.productUpload'), icon: Upload, key: 'productUpload' },
    { path: '/pre-uploaded', label: t('navigation.preUploaded'), icon: Box, key: 'preUploaded' },
  ]

  return (
    <div className="dashboard-layout">
      {/* Mobile menu overlay */}
      {mobileMenuOpen && (
        <div className="nav-overlay" onClick={handleOverlayClick} />
      )}
      
      <nav className={`dashboard-nav ${mobileMenuOpen ? 'mobile-open' : ''}`}>
        <div className="nav-header">
          <div className="nav-brand">
            <h2>MTK Bot Order</h2>
          </div>
          <Button 
            variant="outline" 
            size="small" 
            className="mobile-menu-toggle"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
          >
            {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </Button>
        </div>
        
        <div className={`nav-content ${mobileMenuOpen ? 'open' : ''}`}>
          <div className="nav-links">
            {navItems.map(item => {
              const Icon = item.icon
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`nav-link ${location.pathname === item.path ? 'active' : ''}`}
                >
                  <Icon size={18} className="nav-icon" />
                  <span>{item.label}</span>
                </Link>
              )
            })}
          </div>
          <div className="nav-actions">
            <LanguageSelector />
            <Button variant="outline" size="small" onClick={toggleTheme} aria-label="Toggle theme">
              {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
            </Button>
            <div className="user-info">
              <span>{user?.full_name || user?.username}</span>
              <Button variant="outline" size="small" onClick={logout}>
                <LogOut size={16} className="button-icon" />
                <span>{t('navigation.logout')}</span>
              </Button>
            </div>
          </div>
        </div>
      </nav>
      <main className="dashboard-main">
        <Outlet />
      </main>
    </div>
  )
}


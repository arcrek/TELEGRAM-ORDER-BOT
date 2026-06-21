import { NavLink, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import type { LucideIcon } from 'lucide-react'
import {
  BarChart2, Package, Layers, Star, ShoppingCart, Bell, Upload,
  Database, Gift, Settings, Users, Boxes, Wallet, BookOpen,
  Bot, PanelLeftClose, PanelLeft,
} from 'lucide-react'
import { Tooltip } from '../../shared/components/Tooltip'
import { ROUTE_GROUPS, routesByGroup } from '../routes'
import './Sidebar.css'

const ICON_MAP: Record<string, LucideIcon> = {
  BarChart2, Package, Layers, Star, ShoppingCart, Bell,
  Upload, Database, Gift, Settings, Users, Boxes, Wallet, BookOpen,
}

export interface NavBadgeCounts {
  orders?: number        // unpaid order count
  preUploaded?: 'warn'   // aging/low-stock flag
}

interface SidebarProps {
  collapsed: boolean
  onToggleCollapse: () => void
  badgeCounts?: NavBadgeCounts
  className?: string
}

const ROUTE_KEY_TO_BADGE: Record<string, keyof NavBadgeCounts> = {
  orders: 'orders',
  preUploaded: 'preUploaded',
}

export function Sidebar({ collapsed, onToggleCollapse, badgeCounts = {}, className = '' }: SidebarProps) {
  const { t } = useTranslation()
  const location = useLocation()

  return (
    <nav
      className={`sidebar ${collapsed ? 'sidebar--collapsed' : ''} ${className}`}
      aria-label={t('nav.sidebar', 'Navigation')}
    >
      {/* Logo */}
      <div className="sidebar__logo">
        <Bot size={20} className="sidebar__logo-icon" />
        {!collapsed && <span className="sidebar__logo-text">MTK Admin</span>}
      </div>

      {/* Groups */}
      <div className="sidebar__nav">
        {ROUTE_GROUPS.map(group => {
          const routes = routesByGroup(group.key)
          if (!routes.length) return null
          return (
            <div key={group.key} className="sidebar__group">
              {!collapsed && (
                <p className="sidebar__group-label">{t(group.labelKey, group.key)}</p>
              )}
              {routes.map(route => {
                const Icon = ICON_MAP[route.iconName]
                const isActive = location.pathname.startsWith(route.path)
                const label = t(route.labelKey, route.key)
                const badgeKey = ROUTE_KEY_TO_BADGE[route.key]
                const badgeValue = badgeKey ? badgeCounts[badgeKey] : undefined

                const badge = badgeValue != null ? (
                  badgeValue === 'warn'
                    ? <span className="sidebar__badge sidebar__badge--warn" aria-label="Cần chú ý">!</span>
                    : badgeValue > 0
                      ? <span className="sidebar__badge" aria-label={`${badgeValue} chờ xử lý`}>{badgeValue > 99 ? '99+' : badgeValue}</span>
                      : null
                ) : null

                const navItem = (
                  <NavLink
                    key={route.key}
                    to={route.path}
                    className={({ isActive }) =>
                      `sidebar__item ${isActive ? 'sidebar__item--active' : ''}`
                    }
                    aria-label={collapsed ? label : undefined}
                    aria-current={isActive ? 'page' : undefined}
                  >
                    {Icon && <Icon size={16} className="sidebar__item-icon" />}
                    {!collapsed && <span className="sidebar__item-label">{label}</span>}
                    {badge}
                  </NavLink>
                )

                return collapsed
                  ? <Tooltip key={route.key} content={label} placement="right" delay={300}>{navItem}</Tooltip>
                  : navItem
              })}
            </div>
          )
        })}
      </div>

      {/* Collapse toggle */}
      <div className="sidebar__footer">
        <button
          type="button"
          className="sidebar__collapse-btn"
          onClick={onToggleCollapse}
          aria-label={collapsed ? 'Mở rộng menu' : 'Thu gọn menu'}
        >
          {collapsed ? <PanelLeft size={16} /> : <PanelLeftClose size={16} />}
          {!collapsed && <span>Thu gọn</span>}
        </button>
      </div>
    </nav>
  )
}

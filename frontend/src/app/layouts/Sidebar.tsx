import { NavLink, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import type { LucideIcon } from 'lucide-react'
import {
  BarChart2, Package, Layers, Star, ShoppingCart, Bell, Upload,
  Database, Gift, Settings, Users, Boxes,
  Bot, PanelLeftClose, PanelLeft,
} from 'lucide-react'
import { Tooltip } from '../../shared/components/Tooltip'
import { ROUTE_GROUPS, routesByGroup } from '../routes'
import './Sidebar.css'

const ICON_MAP: Record<string, LucideIcon> = {
  BarChart2, Package, Layers, Star, ShoppingCart, Bell,
  Upload, Database, Gift, Settings, Users, Boxes,
}

interface SidebarProps {
  collapsed: boolean
  onToggleCollapse: () => void
  className?: string
}

export function Sidebar({ collapsed, onToggleCollapse, className = '' }: SidebarProps) {
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

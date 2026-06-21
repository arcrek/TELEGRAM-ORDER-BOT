import { useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Search, Menu, Sun, Moon, Globe, ChevronDown, LogOut, User } from 'lucide-react'
import { useEffect, useState } from 'react'
import { IconButton } from '../../shared/components/IconButton'
import { DropdownMenu, type DropdownMenuItem } from '../../shared/components/DropdownMenu'
import { useTheme } from '../../contexts/ThemeContext'
import { useAuth } from '../../contexts/AuthContext'
import { apiClient } from '../../shared/lib/api'
import { ROUTES } from '../routes'
import './Topbar.css'

interface TopbarProps {
  onMenuClick: () => void
  isMobile: boolean
  onSearchClick: () => void
  className?: string
}

export function Topbar({ onMenuClick, isMobile, onSearchClick, className = '' }: TopbarProps) {
  const { t, i18n } = useTranslation()
  const { resolvedTheme, toggleTheme } = useTheme()
  const { user, logout } = useAuth()
  const location = useLocation()
  const [botOnline, setBotOnline] = useState<boolean | null>(null)

  const currentRoute = ROUTES.find(r => location.pathname.startsWith(r.path))
  const pageTitle = currentRoute ? t(currentRoute.labelKey, currentRoute.key) : ''

  // Derive bot status from whether there are recent orders
  useEffect(() => {
    let cancelled = false
    const check = async () => {
      try {
        const res = await apiClient.get<{ total_orders_today: number }>('/api/statistics/overview', {
          params: { range: '1d' },
        })
        if (!cancelled) setBotOnline(res.data.total_orders_today > 0)
      } catch {
        if (!cancelled) setBotOnline(false)
      }
    }
    check()
    const interval = setInterval(check, 120_000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [])

  const langItems: DropdownMenuItem[] = [
    {
      key: 'vi',
      label: 'Tiếng Việt',
      onClick: () => i18n.changeLanguage('vi'),
    },
    {
      key: 'en',
      label: 'English',
      onClick: () => i18n.changeLanguage('en'),
    },
  ]

  const userItems: DropdownMenuItem[] = [
    {
      key: 'profile',
      label: t('common.profile', 'Hồ sơ'),
      icon: <User />,
      onClick: () => {},
    },
    { key: 'sep', label: '', separator: true },
    {
      key: 'logout',
      label: t('common.logout', 'Đăng xuất'),
      icon: <LogOut />,
      danger: true,
      onClick: logout,
    },
  ]

  const username = (user as { username?: string })?.username ?? 'Admin'

  return (
    <header className={`topbar ${className}`}>
      {/* Left: hamburger (mobile) + breadcrumb */}
      <div className="topbar__left">
        {isMobile && (
          <IconButton
            icon={<Menu />}
            aria-label="Open menu"
            variant="ghost"
            onClick={onMenuClick}
          />
        )}
        <h1 className="topbar__page-title">{pageTitle}</h1>
      </div>

      {/* Bot status pill — only show once status is known */}
      {botOnline !== null && (
        <div
          className={`topbar__bot-status topbar__bot-status--${botOnline ? 'online' : 'offline'}`}
          title={botOnline ? 'Bot đang hoạt động' : 'Bot không có đơn hàng hôm nay'}
        >
          <span className="topbar__bot-dot" />
          <span>{botOnline ? 'Bot online' : 'Bot offline'}</span>
        </div>
      )}

      {/* Right: search, lang, theme, user */}
      <div className="topbar__right">
        <button
          type="button"
          className="topbar__search-btn"
          onClick={onSearchClick}
          aria-label={t('common.search', 'Tìm kiếm')}
        >
          <Search size={14} />
          <span className="topbar__search-text">{t('common.search', 'Tìm kiếm…')}</span>
          <kbd className="topbar__kbd">⌘K</kbd>
        </button>

        <DropdownMenu
          trigger={
            <IconButton
              icon={<Globe size={16} />}
              aria-label={t('common.language', 'Ngôn ngữ')}
              variant="ghost"
              size="sm"
            />
          }
          items={langItems}
          placement="bottom-end"
        />

        <IconButton
          icon={resolvedTheme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          aria-label={resolvedTheme === 'dark' ? t('common.lightMode', 'Sáng') : t('common.darkMode', 'Tối')}
          variant="ghost"
          size="sm"
          onClick={toggleTheme}
        />

        <DropdownMenu
          trigger={
            <button type="button" className="topbar__user-btn" aria-label={`${username} menu`}>
              <span className="topbar__avatar">{username[0]?.toUpperCase()}</span>
              <span className="topbar__username">{username}</span>
              <ChevronDown size={12} />
            </button>
          }
          items={userItems}
          placement="bottom-end"
        />
      </div>
    </header>
  )
}

import { useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Search, Menu, Sun, Moon, Globe, ChevronDown, LogOut, User } from 'lucide-react'
import { IconButton } from '../../shared/components/IconButton'
import { DropdownMenu, type DropdownMenuItem } from '../../shared/components/DropdownMenu'
import { useTheme } from '../../contexts/ThemeContext'
import { useAuth } from '../../contexts/AuthContext'
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

  const currentRoute = ROUTES.find(r => location.pathname.startsWith(r.path))
  const pageTitle = currentRoute ? t(currentRoute.labelKey, currentRoute.key) : ''

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

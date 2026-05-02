import { Outlet } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'
import { MobileDrawer } from './MobileDrawer'
import { CommandPalette } from './CommandPalette'
import { useDisclosure } from '../../shared/hooks/useDisclosure'
import { useMediaQuery } from '../../shared/hooks/useMediaQuery'
import './AppShell.css'

function readCollapsed(): boolean {
  try { return localStorage.getItem('sidebar-collapsed') === 'true' } catch { return false }
}

export function AppShell() {
  const [collapsed, setCollapsed] = useState(readCollapsed)
  const isMobile = useMediaQuery('(max-width: 900px)')
  const drawer = useDisclosure()
  const cmdPalette = useDisclosure()

  useEffect(() => {
    try { localStorage.setItem('sidebar-collapsed', String(collapsed)) } catch { /* noop */ }
  }, [collapsed])

  // Close drawer on route change (mobile)
  useEffect(() => { drawer.close() }, [])

  // ⌘K / Ctrl+K
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        cmdPalette.toggle()
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [cmdPalette])

  return (
    <div
      className="app-shell"
      data-collapsed={isMobile ? 'false' : String(collapsed)}
      data-mobile={String(isMobile)}
    >
      {/* Skip to main content link */}
      <a href="#main-content" className="skip-link">Bỏ qua điều hướng</a>

      {!isMobile && (
        <Sidebar
          collapsed={collapsed}
          onToggleCollapse={() => setCollapsed(v => !v)}
          className="app-shell__sidebar"
        />
      )}

      <Topbar
        onMenuClick={drawer.open}
        isMobile={isMobile}
        onSearchClick={cmdPalette.open}
        className="app-shell__topbar"
      />

      <main id="main-content" className="app-shell__main" tabIndex={-1}>
        <Outlet />
      </main>

      {isMobile && (
        <MobileDrawer
          open={drawer.isOpen}
          onClose={drawer.close}
        />
      )}

      <CommandPalette
        open={cmdPalette.isOpen}
        onClose={cmdPalette.close}
      />
    </div>
  )
}

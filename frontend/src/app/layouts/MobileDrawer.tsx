import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { Sidebar } from './Sidebar'
import { IconButton } from '../../shared/components/IconButton'
import { useFocusTrap } from '../../shared/hooks/useFocusTrap'
import './MobileDrawer.css'

interface MobileDrawerProps {
  open: boolean
  onClose: () => void
}

export function MobileDrawer({ open, onClose }: MobileDrawerProps) {
  const drawerRef = useFocusTrap<HTMLDivElement>(open)

  useEffect(() => {
    if (open) document.body.style.overflow = 'hidden'
    else document.body.style.overflow = ''
    return () => { document.body.style.overflow = '' }
  }, [open])

  if (!open) return null

  return createPortal(
    <div className="mobile-drawer-backdrop" onClick={onClose}>
      <div
        ref={drawerRef}
        className="mobile-drawer"
        onClick={e => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Navigation menu"
      >
        <div className="mobile-drawer__close">
          <IconButton icon={<X />} aria-label="Close menu" variant="ghost" onClick={onClose} />
        </div>
        <Sidebar
          collapsed={false}
          onToggleCollapse={onClose}
          className="mobile-drawer__sidebar"
        />
      </div>
    </div>,
    document.body,
  )
}

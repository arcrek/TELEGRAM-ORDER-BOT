import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { AlertTriangle, Info, Trash2 } from 'lucide-react'
import { Modal } from '../Modal'
import { Button } from '../Button'
import './ConfirmDialog.css'

export type ConfirmVariant = 'default' | 'destructive' | 'warning'

export interface ConfirmOptions {
  title: string
  description?: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: ConfirmVariant
}

type ConfirmFn = (options: ConfirmOptions) => Promise<boolean>

const ConfirmContext = createContext<ConfirmFn | null>(null)

interface DialogState extends ConfirmOptions {
  resolve: (value: boolean) => void
}

export function ConfirmDialogProvider({ children }: { children: ReactNode }) {
  const [dialog, setDialog] = useState<DialogState | null>(null)
  const confirm = useCallback<ConfirmFn>((options) => {
    return new Promise<boolean>(resolve => {
      setDialog({ ...options, resolve })
    })
  }, [])

  const handleClose = (confirmed: boolean) => {
    dialog?.resolve(confirmed)
    setDialog(null)
  }

  const variant = dialog?.variant ?? 'default'
  const icons: Record<ConfirmVariant, ReactNode> = {
    default: <Info size={20} />,
    warning: <AlertTriangle size={20} />,
    destructive: <Trash2 size={20} />,
  }

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {dialog && (
        <Modal
          open
          onClose={() => handleClose(false)}
          size="sm"
          hideCloseButton
          closeOnBackdrop={false}
        >
          <div className={`confirm-dialog confirm-dialog--${variant}`}>
            <div className="confirm-dialog__icon">{icons[variant]}</div>
            <div className="confirm-dialog__content">
              <p className="confirm-dialog__title">{dialog.title}</p>
              {dialog.description && (
                <p className="confirm-dialog__description">{dialog.description}</p>
              )}
            </div>
          </div>
          <div className="confirm-dialog__actions">
            <Button
              variant="secondary"
              tone="solid"
              size="sm"
              onClick={() => handleClose(false)}
            >
              {dialog.cancelLabel ?? 'Huỷ'}
            </Button>
            <Button
              variant={variant === 'destructive' ? 'destructive' : 'primary'}
              tone="solid"
              size="sm"
              onClick={() => handleClose(true)}
            >
              {dialog.confirmLabel ?? 'Xác nhận'}
            </Button>
          </div>
        </Modal>
      )}
    </ConfirmContext.Provider>
  )
}

export function useConfirm(): ConfirmFn {
  const ctx = useContext(ConfirmContext)
  if (!ctx) throw new Error('useConfirm must be used within ConfirmDialogProvider')
  return ctx
}

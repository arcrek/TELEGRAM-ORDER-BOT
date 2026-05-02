import { useState, useRef, type ReactNode, type DragEvent, type ChangeEvent } from 'react'
import { UploadCloud, X } from 'lucide-react'
import './FileDrop.css'

export interface FileDropProps {
  accept?: string
  maxSize?: number
  multiple?: boolean
  onFiles: (files: File[]) => void
  onError?: (msg: string) => void
  label?: string
  hint?: string
  disabled?: boolean
  className?: string
  children?: ReactNode
}

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function FileDrop({
  accept,
  maxSize,
  multiple = false,
  onFiles,
  onError,
  label = 'Kéo thả hoặc click để chọn file',
  hint,
  disabled = false,
  className = '',
}: FileDropProps) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement | null>(null)

  const validateAndEmit = (files: FileList | File[]) => {
    const arr = Array.from(files)
    const invalid = maxSize ? arr.filter(f => f.size > maxSize) : []
    if (invalid.length > 0) {
      onError?.(`File quá lớn (tối đa ${humanSize(maxSize!)})`)
      return
    }
    onFiles(arr)
  }

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragging(false)
    if (disabled) return
    validateAndEmit(e.dataTransfer.files)
  }

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) validateAndEmit(e.target.files)
    e.target.value = ''
  }

  const handlePaste = (e: React.ClipboardEvent<HTMLDivElement>) => {
    if (disabled || !e.clipboardData.files.length) return
    validateAndEmit(e.clipboardData.files)
  }

  return (
    <div
      className={`filedrop ${dragging ? 'filedrop--dragging' : ''} ${disabled ? 'filedrop--disabled' : ''} ${className}`}
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onPaste={handlePaste}
      onClick={() => !disabled && inputRef.current?.click()}
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-label={label}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); inputRef.current?.click() } }}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        className="filedrop__input"
        onChange={handleChange}
        tabIndex={-1}
        aria-hidden="true"
      />
      <div className="filedrop__content">
        <UploadCloud size={28} className="filedrop__icon" />
        <p className="filedrop__label">{label}</p>
        {hint && <p className="filedrop__hint">{hint}</p>}
        {accept && <p className="filedrop__accept">{accept}</p>}
      </div>
    </div>
  )
}

export interface FileChipProps {
  file: File
  onRemove: () => void
}

export function FileChip({ file, onRemove }: FileChipProps) {
  return (
    <div className="file-chip">
      <span className="file-chip__name">{file.name}</span>
      <span className="file-chip__size">{humanSize(file.size)}</span>
      <button type="button" className="file-chip__remove" onClick={onRemove} aria-label={`Remove ${file.name}`}>
        <X size={12} />
      </button>
    </div>
  )
}

import { ChevronLeft, ChevronRight } from 'lucide-react'
import { IconButton } from '../IconButton'
import './Pagination.css'

export interface PaginationProps {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
  onPageSizeChange?: (size: number) => void
  pageSizeOptions?: number[]
  className?: string
}

export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 25, 50, 100],
  className = '',
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const from = Math.min((page - 1) * pageSize + 1, total)
  const to = Math.min(page * pageSize, total)

  return (
    <nav className={`pagination ${className}`} aria-label="Pagination">
      <span className="pagination__count">
        {total === 0 ? '0' : `${from}–${to}`} / {total}
      </span>

      {onPageSizeChange && (
        <label className="pagination__size-label">
          <span className="pagination__size-text">Rows</span>
          <select
            className="pagination__size-select"
            value={pageSize}
            onChange={e => {
              onPageSizeChange(Number(e.target.value))
              onPageChange(1)
            }}
            aria-label="Rows per page"
          >
            {pageSizeOptions.map(opt => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
        </label>
      )}

      <div className="pagination__nav">
        <IconButton
          icon={<ChevronLeft />}
          aria-label="Previous page"
          size="sm"
          variant="ghost"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        />
        <span className="pagination__pages" aria-current="page">
          {page} / {totalPages}
        </span>
        <IconButton
          icon={<ChevronRight />}
          aria-label="Next page"
          size="sm"
          variant="ghost"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        />
      </div>
    </nav>
  )
}

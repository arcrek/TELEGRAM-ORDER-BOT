import { useState, type ReactNode } from 'react'
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react'
import { Checkbox } from '../Checkbox'
import { Skeleton } from '../Skeleton'
import { EmptyState } from '../EmptyState'
import './Table.css'

export type SortDirection = 'asc' | 'desc' | null

export interface ColumnDef<T> {
  id: string
  header: ReactNode
  accessor?: keyof T
  cell?: (row: T, idx: number) => ReactNode
  sortable?: boolean
  width?: number | string
  minWidth?: number
  align?: 'left' | 'center' | 'right'
  sticky?: boolean
  mono?: boolean
  hidden?: boolean
}

export interface SortState {
  id: string
  direction: SortDirection
}

export interface TableProps<T> {
  columns: ColumnDef<T>[]
  data: T[]
  keyFn: (row: T) => string
  loading?: boolean
  skeletonRows?: number
  emptyIcon?: ReactNode
  emptyTitle?: string
  emptyDescription?: string
  emptyAction?: ReactNode
  selectable?: boolean
  selectedKeys?: Set<string>
  onSelectionChange?: (keys: Set<string>) => void
  sortState?: SortState
  onSortChange?: (sort: SortState) => void
  density?: 'comfortable' | 'compact'
  stickyHeader?: boolean
  className?: string
  onRowClick?: (row: T) => void
}

export function Table<T>({
  columns,
  data,
  keyFn,
  loading = false,
  skeletonRows = 5,
  emptyIcon,
  emptyTitle = 'Không có dữ liệu',
  emptyDescription,
  emptyAction,
  selectable = false,
  selectedKeys,
  onSelectionChange,
  sortState,
  onSortChange,
  density = 'comfortable',
  stickyHeader = false,
  className = '',
  onRowClick,
}: TableProps<T>) {
  const [internalSort, setInternalSort] = useState<SortState | null>(null)
  const activeSort = sortState ?? internalSort
  const visibleCols = columns.filter(c => !c.hidden)

  const handleSort = (col: ColumnDef<T>) => {
    if (!col.sortable) return
    const current = activeSort?.id === col.id ? activeSort.direction : null
    const next: SortDirection = current === null ? 'asc' : current === 'asc' ? 'desc' : null
    const newSort: SortState = { id: col.id, direction: next }
    if (onSortChange) {
      onSortChange(newSort)
    } else {
      setInternalSort(next === null ? null : newSort)
    }
  }

  const allKeys = data.map(keyFn)
  const allSelected = allKeys.length > 0 && allKeys.every(k => selectedKeys?.has(k))
  const someSelected = allKeys.some(k => selectedKeys?.has(k))

  const toggleAll = (checked: boolean) => {
    if (!onSelectionChange) return
    onSelectionChange(checked ? new Set(allKeys) : new Set())
  }

  const toggleRow = (key: string, checked: boolean) => {
    if (!onSelectionChange || !selectedKeys) return
    const next = new Set(selectedKeys)
    checked ? next.add(key) : next.delete(key)
    onSelectionChange(next)
  }

  const isEmpty = !loading && data.length === 0

  return (
    <div className={`table-wrap ${stickyHeader ? 'table-wrap--sticky-header' : ''} ${className}`}>
      <table
        className={`table table--${density}`}
        aria-busy={loading}
      >
        <thead className="table__head">
          <tr>
            {selectable && (
              <th className="table__th table__th--check" scope="col">
                <Checkbox
                  checked={allSelected}
                  indeterminate={someSelected && !allSelected}
                  onChange={toggleAll}
                  aria-label="Select all rows"
                />
              </th>
            )}
            {visibleCols.map(col => {
              const sortDir = activeSort?.id === col.id ? activeSort.direction : null
              return (
                <th
                  key={col.id}
                  scope="col"
                  className={[
                    'table__th',
                    col.sortable && 'table__th--sortable',
                    col.sticky && 'table__th--sticky',
                    col.mono && 'table__th--mono',
                    col.align && `table__th--${col.align}`,
                  ].filter(Boolean).join(' ')}
                  style={{
                    width: col.width,
                    minWidth: col.minWidth,
                  }}
                  aria-sort={
                    col.sortable
                      ? sortDir === 'asc' ? 'ascending'
                        : sortDir === 'desc' ? 'descending'
                        : 'none'
                      : undefined
                  }
                  onClick={col.sortable ? () => handleSort(col) : undefined}
                >
                  <span className="table__th-inner">
                    {col.header}
                    {col.sortable && (
                      <span className="table__sort-icon" aria-hidden="true">
                        {sortDir === 'asc' ? <ChevronUp size={12} /> :
                          sortDir === 'desc' ? <ChevronDown size={12} /> :
                          <ChevronsUpDown size={12} />}
                      </span>
                    )}
                  </span>
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody className="table__body">
          {loading
            ? Array.from({ length: skeletonRows }).map((_, i) => (
                <tr key={i} className="table__row table__row--skeleton">
                  {selectable && <td className="table__td table__td--check"><Skeleton variant="rect" width={16} height={16} radius="4px" /></td>}
                  {visibleCols.map(col => (
                    <td key={col.id} className="table__td">
                      <Skeleton variant="line" width="80%" height={14} />
                    </td>
                  ))}
                </tr>
              ))
            : data.map((row, idx) => {
                const key = keyFn(row)
                const isSelected = selectedKeys?.has(key) ?? false
                return (
                  <tr
                    key={key}
                    className={[
                      'table__row',
                      isSelected && 'table__row--selected',
                      onRowClick && 'table__row--clickable',
                    ].filter(Boolean).join(' ')}
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                    aria-selected={selectable ? isSelected : undefined}
                  >
                    {selectable && (
                      <td className="table__td table__td--check" onClick={e => e.stopPropagation()}>
                        <Checkbox
                          checked={isSelected}
                          onChange={checked => toggleRow(key, checked)}
                          aria-label={`Select row ${idx + 1}`}
                        />
                      </td>
                    )}
                    {visibleCols.map(col => (
                      <td
                        key={col.id}
                        className={[
                          'table__td',
                          col.sticky && 'table__td--sticky',
                          col.mono && 'table__td--mono',
                          col.align && `table__td--${col.align}`,
                        ].filter(Boolean).join(' ')}
                        style={{ width: col.width, minWidth: col.minWidth }}
                      >
                        {col.cell
                          ? col.cell(row, idx)
                          : col.accessor
                          ? String(row[col.accessor] ?? '')
                          : null}
                      </td>
                    ))}
                  </tr>
                )
              })}
        </tbody>
      </table>

      {isEmpty && (
        <div className="table__empty">
          <EmptyState
            icon={emptyIcon}
            title={emptyTitle}
            description={emptyDescription}
            action={emptyAction}
          />
        </div>
      )}
    </div>
  )
}

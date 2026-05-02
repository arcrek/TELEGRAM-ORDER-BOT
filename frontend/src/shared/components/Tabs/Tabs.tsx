import {
  useState,
  useRef,
  type ReactNode,
  type KeyboardEvent,
  type ComponentType,
  type LazyExoticComponent,
} from 'react'
import './Tabs.css'

export interface TabItem {
  key: string
  label: ReactNode
  panel: ReactNode | (() => ReactNode) | ComponentType | LazyExoticComponent<ComponentType>
  disabled?: boolean
  badge?: ReactNode
}

export interface TabsProps {
  tabs: TabItem[]
  defaultKey?: string
  activeKey?: string
  onChange?: (key: string) => void
  className?: string
  panelClassName?: string
  variant?: 'underline' | 'pill'
  size?: 'sm' | 'md'
  lazy?: boolean
}

export function Tabs({
  tabs,
  defaultKey,
  activeKey: controlledKey,
  onChange,
  className = '',
  panelClassName = '',
  variant = 'underline',
  size = 'md',
  lazy = false,
}: TabsProps) {
  const [internalKey, setInternalKey] = useState(defaultKey ?? tabs[0]?.key ?? '')
  const activeKey = controlledKey ?? internalKey
  const tabRefs = useRef<Map<string, HTMLButtonElement>>(new Map())
  const activatedRef = useRef<Set<string>>(new Set([activeKey]))

  const handleSelect = (key: string) => {
    if (!controlledKey) setInternalKey(key)
    activatedRef.current.add(key)
    onChange?.(key)
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const enabledKeys = tabs.filter(t => !t.disabled).map(t => t.key)
    const idx = enabledKeys.indexOf(activeKey)
    if (e.key === 'ArrowRight') {
      e.preventDefault()
      const next = enabledKeys[(idx + 1) % enabledKeys.length]
      handleSelect(next)
      tabRefs.current.get(next)?.focus()
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault()
      const prev = enabledKeys[(idx - 1 + enabledKeys.length) % enabledKeys.length]
      handleSelect(prev)
      tabRefs.current.get(prev)?.focus()
    }
  }

  const activeTab = tabs.find(t => t.key === activeKey)

  const renderPanel = (tab: TabItem) => {
    const Panel = tab.panel
    if (!Panel) return null
    if (typeof Panel === 'function' && Panel.length === 0 && !(Panel as ComponentType).prototype?.render) {
      return (Panel as () => ReactNode)()
    }
    if (typeof Panel === 'function') {
      const Cmp = Panel as ComponentType
      return <Cmp />
    }
    return Panel as ReactNode
  }

  return (
    <div className={`tabs tabs--${variant} tabs--${size} ${className}`}>
      <div
        role="tablist"
        className="tabs__list"
        onKeyDown={handleKeyDown}
        aria-orientation="horizontal"
      >
        {tabs.map(tab => (
          <button
            key={tab.key}
            role="tab"
            id={`tab-${tab.key}`}
            aria-selected={tab.key === activeKey}
            aria-controls={`tabpanel-${tab.key}`}
            disabled={tab.disabled}
            className={`tabs__tab ${tab.key === activeKey ? 'tabs__tab--active' : ''}`}
            tabIndex={tab.key === activeKey ? 0 : -1}
            ref={el => {
              if (el) tabRefs.current.set(tab.key, el)
              else tabRefs.current.delete(tab.key)
            }}
            onClick={() => handleSelect(tab.key)}
          >
            {tab.label}
            {tab.badge && <span className="tabs__tab-badge">{tab.badge}</span>}
          </button>
        ))}
      </div>

      {lazy
        ? tabs.map(tab => {
            const wasActivated = activatedRef.current.has(tab.key)
            const isActive = tab.key === activeKey
            if (!wasActivated && !isActive) return null
            return (
              <div
                key={tab.key}
                role="tabpanel"
                id={`tabpanel-${tab.key}`}
                aria-labelledby={`tab-${tab.key}`}
                className={`tabs__panel ${panelClassName} ${isActive ? 'tabs__panel--active' : 'tabs__panel--hidden'}`}
                hidden={!isActive}
                tabIndex={0}
              >
                {renderPanel(tab)}
              </div>
            )
          })
        : activeTab && (
            <div
              role="tabpanel"
              id={`tabpanel-${activeTab.key}`}
              aria-labelledby={`tab-${activeTab.key}`}
              className={`tabs__panel tabs__panel--active ${panelClassName}`}
              tabIndex={0}
            >
              {renderPanel(activeTab)}
            </div>
          )}
    </div>
  )
}

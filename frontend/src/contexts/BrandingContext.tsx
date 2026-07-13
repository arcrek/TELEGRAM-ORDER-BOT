import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { apiClient } from '../shared/lib/api'

interface BrandingValue {
  systemName: string
  refresh: () => Promise<void>
}

const BrandingContext = createContext<BrandingValue | null>(null)

export function BrandingProvider({ children }: { children: ReactNode }) {
  const [systemName, setSystemName] = useState('Bot Order Admin')
  const refresh = useCallback(async () => {
    try {
      const response = await apiClient.get<{ system_name: string }>('/api/app-settings/public')
      if (response.data.system_name.trim()) setSystemName(response.data.system_name.trim())
    } catch {
      // The generic fallback remains usable when the public endpoint is unavailable.
    }
  }, [])

  useEffect(() => { void refresh() }, [refresh])

  const value = useMemo(() => ({ systemName, refresh }), [systemName, refresh])
  return <BrandingContext.Provider value={value}>{children}</BrandingContext.Provider>
}

export function useBranding(): BrandingValue {
  const value = useContext(BrandingContext)
  if (!value) throw new Error('useBranding must be used inside BrandingProvider')
  return value
}

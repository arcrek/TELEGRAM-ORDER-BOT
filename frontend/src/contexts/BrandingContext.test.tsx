import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from '../shared/lib/api'
import { BrandingProvider, useBranding } from './BrandingContext'

vi.mock('../shared/lib/api', () => ({
  apiClient: { get: vi.fn() },
}))

function Probe() {
  const { systemName } = useBranding()
  return <span>{systemName}</span>
}

describe('BrandingProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    document.title = 'stale title'
  })

  it('loads the public system name', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { system_name: 'Example Shop' } })
    render(<BrandingProvider><Probe /></BrandingProvider>)
    await waitFor(() => expect(screen.getByText('Example Shop')).toBeInTheDocument())
    expect(document.title).toBe('Example Shop')
  })

  it('keeps a generic fallback when the API is unavailable', async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error('offline'))
    render(<BrandingProvider><Probe /></BrandingProvider>)
    expect(screen.getByText('Bot Order Admin')).toBeInTheDocument()
    await waitFor(() => expect(document.title).toBe('Bot Order Admin'))
  })
})

import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { BrandingProvider } from '../contexts/BrandingContext'
import i18n from '../i18n/config'
import { ToastProvider } from '../shared/components/Toast'
import { apiClient } from '../shared/lib/api'
import { GeneralSettingsPage } from './GeneralSettingsPage'

vi.mock('../shared/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../shared/lib/api')>()
  return {
    ...actual,
    apiClient: { get: vi.fn(), put: vi.fn() },
  }
})

const settings = {
  system_name: 'Example Shop',
  bot_url: 'https://t.me/example_shop_bot',
  support_line_1: '@support',
  support_line_2: '',
  timezone: 'UTC',
  order_prefix: 'SHOP',
  api_docs_url: 'https://shop.example/api',
}

describe('GeneralSettingsPage', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    await i18n.changeLanguage('en')
    vi.mocked(apiClient.get).mockResolvedValue({ data: settings })
    vi.mocked(apiClient.put).mockResolvedValue({ data: settings })
  })

  it('loads, edits, and saves the complete settings payload', async () => {
    render(
      <BrandingProvider>
        <ToastProvider>
          <GeneralSettingsPage />
        </ToastProvider>
      </BrandingProvider>,
    )

    expect(await screen.findByLabelText('System name')).toHaveValue('Example Shop')
    expect(apiClient.get).toHaveBeenCalledWith('/api/app-settings')

    fireEvent.change(screen.getByLabelText('System name'), { target: { value: 'Changed Shop' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(apiClient.put).toHaveBeenCalledWith('/api/app-settings', {
        system_name: 'Changed Shop',
        bot_url: 'https://t.me/example_shop_bot',
        support_line_1: '@support',
        support_line_2: '',
        timezone: 'UTC',
        order_prefix: 'SHOP',
        api_docs_url: 'https://shop.example/api',
      })
    })
  })
})

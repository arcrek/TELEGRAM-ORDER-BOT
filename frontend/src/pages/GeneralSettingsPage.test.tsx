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

function renderPage() {
  render(
    <BrandingProvider>
      <ToastProvider>
        <GeneralSettingsPage />
      </ToastProvider>
    </BrandingProvider>,
  )
}

function publicBrandingGetCount() {
  return vi.mocked(apiClient.get).mock.calls.filter(([url]) => url === '/api/app-settings/public').length
}

describe('GeneralSettingsPage', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    await i18n.changeLanguage('en')
    vi.mocked(apiClient.get).mockResolvedValue({ data: settings })
    vi.mocked(apiClient.put).mockResolvedValue({ data: settings })
  })

  it('loads, edits, and saves the complete normalized settings payload', async () => {
    const normalized = { ...settings, system_name: 'Changed Shop', order_prefix: 'SHOP2' }
    vi.mocked(apiClient.put).mockResolvedValue({ data: normalized })
    renderPage()
    expect(await screen.findByLabelText('System name')).toHaveValue('Example Shop')
    expect(apiClient.get).toHaveBeenCalledWith('/api/app-settings')

    fireEvent.change(screen.getByLabelText('System name'), { target: { value: ' Changed Shop ' } })
    fireEvent.change(screen.getByLabelText('Order prefix'), { target: { value: 'shop2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(apiClient.put).toHaveBeenCalledWith('/api/app-settings', {
        system_name: ' Changed Shop ',
        bot_url: 'https://t.me/example_shop_bot',
        support_line_1: '@support',
        support_line_2: '',
        timezone: 'UTC',
        order_prefix: 'shop2',
        api_docs_url: 'https://shop.example/api',
      })
    })
    expect(screen.getByLabelText('System name')).toHaveValue('Changed Shop')
    expect(screen.getByLabelText('Order prefix')).toHaveValue('SHOP2')
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
  })

  it('blocks button submission when a native field constraint is invalid', async () => {
    renderPage()
    await screen.findByLabelText('System name')

    fireEvent.change(screen.getByLabelText('Bot URL'), { target: { value: 'not-a-url' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect(apiClient.put).not.toHaveBeenCalled()
  })

  it('blocks Ctrl+S submission when a native field constraint is invalid', async () => {
    renderPage()
    await screen.findByLabelText('System name')

    fireEvent.change(screen.getByLabelText('Bot URL'), { target: { value: 'not-a-url' } })
    fireEvent.keyDown(document, { key: 's', ctrlKey: true })

    expect(apiClient.put).not.toHaveBeenCalled()
  })

  it('refreshes public branding after a successful save', async () => {
    renderPage()
    await screen.findByLabelText('System name')
    await waitFor(() => expect(publicBrandingGetCount()).toBe(1))

    fireEvent.change(screen.getByLabelText('System name'), { target: { value: 'Changed Shop' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(publicBrandingGetCount()).toBe(2))
  })
})

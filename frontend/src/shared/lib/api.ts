/**
 * Centralized axios client.
 * - Reads bearer token from localStorage('token') and injects on every request.
 * - On 401, clears auth state and redirects to /login (with a toast).
 * - Pages should import { apiClient } and stop reading localStorage themselves.
 */
import axios, {
  AxiosError,
  AxiosInstance,
  AxiosRequestConfig,
  InternalAxiosRequestConfig,
} from 'axios'

type ToastFn = (message: string) => void

let toastErrorImpl: ToastFn = () => {}
export function setToastErrorHandler(fn: ToastFn) {
  toastErrorImpl = fn
}

let unauthorizedHandler: () => void = () => {}
export function setUnauthorizedHandler(fn: () => void) {
  unauthorizedHandler = fn
}

const TOKEN_KEY = 'token'

export function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(TOKEN_KEY)
}

export function clearAuthToken(): void {
  if (typeof window === 'undefined') return
  localStorage.removeItem(TOKEN_KEY)
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAuthToken()
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (resp) => resp,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      clearAuthToken()
      toastErrorImpl('Your session has expired. Please log in again.')
      unauthorizedHandler()
    }
    return Promise.reject(error)
  },
)

/** Extract the most useful error string from an axios failure. */
export function formatApiError(err: unknown, fallback = 'Something went wrong'): string {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data as { detail?: string | Array<{ msg?: string; message?: string }>; message?: string } | undefined
    if (Array.isArray(data?.detail)) {
      const first = data?.detail[0]
      return first?.msg || first?.message || fallback
    }
    return (typeof data?.detail === 'string' ? data.detail : null) || data?.message || err.message || fallback
  }
  if (err instanceof Error) return err.message
  return fallback
}

export type { AxiosRequestConfig }

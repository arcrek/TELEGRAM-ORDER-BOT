import { useState, useId } from 'react'
import { useNavigate } from 'react-router-dom'
import { Eye, EyeOff, Lock } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../contexts/AuthContext'
import { useBranding } from '../contexts/BrandingContext'
import { Button } from '../shared/components/Button'
import { Input } from '../shared/components/Input'
import { FormField } from '../shared/components/FormField'
import './LoginPage.css'

export function LoginPage() {
  const { t } = useTranslation()
  const { login } = useAuth()
  const { systemName } = useBranding()
  const navigate = useNavigate()
  const formId = useId()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
      navigate('/')
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || t('auth.loginFailed', 'Sai tên đăng nhập hoặc mật khẩu'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-page__brand">
        <div className="login-page__brand-inner">
          <div className="login-page__logo">
            <Lock size={24} />
          </div>
          <h1 className="login-page__brand-title">{systemName}</h1>
          <p className="login-page__brand-sub">{t('auth.brandTagline', 'Hệ thống quản lý đơn hàng Telegram')}</p>
        </div>
      </div>

      <div className="login-page__form-col">
        <div className="login-page__card">
          <h2 className="login-page__title">{t('auth.signIn', 'Đăng nhập')}</h2>
          <p className="login-page__subtitle">{t('auth.signInDesc', 'Nhập thông tin đăng nhập admin')}</p>

          <form id={formId} onSubmit={handleSubmit} className="login-page__form">
            {error && (
              <div className="login-page__error" role="alert">{error}</div>
            )}

            <FormField label={t('auth.username', 'Tên đăng nhập')} htmlFor={`${formId}-user`}>
              <Input
                id={`${formId}-user`}
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder={t('auth.usernamePlaceholder', 'admin')}
                autoComplete="username"
                disabled={loading}
                required
              />
            </FormField>

            <FormField label={t('auth.password', 'Mật khẩu')} htmlFor={`${formId}-pass`}>
              <Input
                id={`${formId}-pass`}
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
                disabled={loading}
                required
                rightIcon={
                  <button
                    type="button"
                    className="login-page__eye"
                    onClick={() => setShowPassword(v => !v)}
                    aria-label={showPassword ? t('auth.hidePassword', 'Ẩn mật khẩu') : t('auth.showPassword', 'Hiện mật khẩu')}
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                }
              />
            </FormField>

            <Button
              type="submit"
              variant="primary"
              size="md"
              loading={loading}
              className="login-page__submit"
            >
              {t('auth.signIn', 'Đăng nhập')}
            </Button>
          </form>
        </div>
      </div>
    </div>
  )
}

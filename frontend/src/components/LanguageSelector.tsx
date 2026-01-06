/**
 * Language selector component.
 */
import { useTranslation } from 'react-i18next'
import { Select } from './Select'
import './LanguageSelector.css'

export function LanguageSelector() {
  const { i18n } = useTranslation()

  const handleLanguageChange = (value: string | number | boolean | null) => {
    const langValue = typeof value === 'string' ? value : null
    if (langValue && (langValue === 'en' || langValue === 'vi')) {
      i18n.changeLanguage(langValue)
      // Save to localStorage (i18next handles this automatically)
    }
  }

  const options = [
    { value: 'en', label: '🇬🇧 English' },
    { value: 'vi', label: '🇻🇳 Tiếng Việt' },
  ]

  return (
    <div className="language-selector">
      <Select
        options={options}
        value={i18n.language || 'en'}
        onChange={handleLanguageChange}
        placeholder="Select Language"
      />
    </div>
  )
}


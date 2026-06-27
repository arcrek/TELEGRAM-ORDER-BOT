/**
 * i18next configuration.
 * Single 'translation' namespace composed from per-feature JSON files,
 * so existing pages keep using nested keys (t('common.loading') etc.).
 * Future page rebuilds may opt into proper per-namespace splits.
 */
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'

import viCommon from './locales/vi/common.json'
import viNav from './locales/vi/nav.json'
import viAuth from './locales/vi/auth.json'
import viStatistics from './locales/vi/statistics.json'
import viProducts from './locales/vi/products.json'
import viOrders from './locales/vi/orders.json'
import viNotifications from './locales/vi/notifications.json'
import viInventory from './locales/vi/inventory.json'
import viEmoji from './locales/vi/emoji.json'
import viRefunds from './locales/vi/refunds.json'

import enCommon from './locales/en/common.json'
import enNav from './locales/en/nav.json'
import enAuth from './locales/en/auth.json'
import enStatistics from './locales/en/statistics.json'
import enProducts from './locales/en/products.json'
import enOrders from './locales/en/orders.json'
import enNotifications from './locales/en/notifications.json'
import enInventory from './locales/en/inventory.json'
import enEmoji from './locales/en/emoji.json'
import enRefunds from './locales/en/refunds.json'

const viTranslations = {
  ...viCommon,
  ...viNav,
  ...viAuth,
  ...viStatistics,
  ...viProducts,
  ...viOrders,
  ...viNotifications,
  ...viInventory,
  ...viEmoji,
  ...viRefunds,
}

const enTranslations = {
  ...enCommon,
  ...enNav,
  ...enAuth,
  ...enStatistics,
  ...enProducts,
  ...enOrders,
  ...enNotifications,
  ...enInventory,
  ...enEmoji,
  ...enRefunds,
}

// Seed Vietnamese as the default for first-time visitors only;
// never overwrite an explicit user choice already in localStorage.
if (typeof window !== 'undefined' && !localStorage.getItem('i18nextLng')) {
  localStorage.setItem('i18nextLng', 'vi')
}

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: enTranslations },
      vi: { translation: viTranslations },
    },
    fallbackLng: 'vi',
    supportedLngs: ['vi', 'en'],
    load: 'languageOnly',
    defaultNS: 'translation',
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
    },
  })

export default i18n

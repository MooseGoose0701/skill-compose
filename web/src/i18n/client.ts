'use client'

import i18next from 'i18next'
import { initReactI18next, useTranslation as useTranslationOrg } from 'react-i18next'
import { languages, fallbackLng, Language, cookieName, defaultNS } from './settings'
import { resources } from './resources'

const runsOnServerSide = typeof window === 'undefined'

// Get language from cookie
function getLanguageFromCookie(): Language {
  if (runsOnServerSide) return fallbackLng

  const match = document.cookie.match(new RegExp(`(^| )${cookieName}=([^;]+)`))
  const lang = match ? match[2] : null

  if (lang && languages.includes(lang as Language)) {
    return lang as Language
  }
  return fallbackLng
}

// Set language cookie
export function setLanguageCookie(lang: Language) {
  document.cookie = `${cookieName}=${lang};path=/;max-age=31536000` // 1 year
}

// Initialize i18next synchronously at module level — no flash on first render
const language = getLanguageFromCookie()

i18next
  .use(initReactI18next)
  .init({
    resources,
    supportedLngs: languages,
    fallbackLng,
    lng: language,
    fallbackNS: defaultNS,
    defaultNS,
    ns: Object.keys(resources[fallbackLng]),
    interpolation: {
      escapeValue: false, // React already escapes
    },
  })

// Export useTranslation hook
export function useTranslation(ns?: string | string[], options?: { keyPrefix?: string }) {
  return useTranslationOrg(ns, options)
}

// Export changeLanguage function
export function changeLanguage(lng: Language) {
  setLanguageCookie(lng)
  // Reload to apply new language — i18next re-initializes from cookie on load
  window.location.reload()
}

// Export current language getter
export function getCurrentLanguage(): Language {
  if (runsOnServerSide) return fallbackLng
  return (i18next.language as Language) || getLanguageFromCookie()
}

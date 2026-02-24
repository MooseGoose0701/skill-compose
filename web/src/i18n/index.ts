// Re-export from settings
export {
  fallbackLng,
  languages,
  languageNames,
  defaultNS,
  cookieName,
  getOptions,
  type Language
} from './settings'

// Re-export from client
export {
  useTranslation,
  changeLanguage,
  getCurrentLanguage,
  setLanguageCookie
} from './client'

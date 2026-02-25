import type { TFunction } from 'i18next';

/**
 * Get the translated description for a seeded agent or skill.
 * Falls back to the raw DB description for non-seeded (user-created) items.
 */
export function getSeedDescription(
  t: TFunction,
  name: string,
  dbDescription?: string | null
): string {
  const key = `seedDescriptions.${name}`;
  const translated = t(key, { defaultValue: '' });
  if (translated && translated !== key && translated !== '') {
    return translated;
  }
  return dbDescription || '';
}

/** Alias for readability in agent contexts */
export const getAgentDescription = getSeedDescription;

/** Alias for readability in skill contexts */
export const getSkillDescription = getSeedDescription;

/**
 * Get display name for a seeded agent: "OriginalName (TranslatedName)"
 * Returns just the original name if no translation exists or language is English.
 */
export function getAgentDisplayName(
  t: TFunction,
  name: string
): string {
  const key = `seedNames.${name}`;
  const translated = t(key, { defaultValue: '' });
  if (translated && translated !== key && translated !== '') {
    return `${name} (${translated})`;
  }
  return name;
}

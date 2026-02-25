import { Badge } from "@/components/ui/badge";
import { useTranslation } from "@/i18n/client";

export function SkillTypeBadge({ skillType }: { skillType?: string }) {
  const { t } = useTranslation('skills');
  if (skillType === 'meta') {
    return (
      <Badge variant="outline-purple">
        {t('type.meta')}
      </Badge>
    );
  }
  return (
    <Badge variant="outline-info">
      {t('type.user')}
    </Badge>
  );
}

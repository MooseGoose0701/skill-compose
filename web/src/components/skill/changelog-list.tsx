"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useTranslation } from "@/i18n/client";
import { formatDateTime } from "@/lib/formatters";
import type { SkillChangelog } from "@/types/skill";

interface ChangelogListProps {
  changelogs: SkillChangelog[];
  isLoading: boolean;
}

export function ChangelogList({ changelogs, isLoading }: ChangelogListProps) {
  const { t } = useTranslation('skills');

  if (isLoading) {
    return <p className="text-muted-foreground">{t('changelog.loading')}</p>;
  }

  if (changelogs.length === 0) {
    return <p className="text-muted-foreground">{t('changelog.empty')}</p>;
  }

  const changeTypeVariants: Record<string, "success" | "info" | "warning" | "error" | "secondary"> = {
    create: "success",
    update: "info",
    rollback: "warning",
    delete: "error",
  };

  return (
    <div className="space-y-3">
      {changelogs.map((entry) => (
        <Card key={entry.id}>
          <CardContent className="p-4">
            <div className="flex items-start justify-between">
              <div>
                <Badge
                  variant={changeTypeVariants[entry.change_type] || "secondary"}
                >
                  {entry.change_type}
                </Badge>
                {entry.version_from && entry.version_to && (
                  <span className="ml-2 text-sm text-muted-foreground">
                    {entry.version_from} → {entry.version_to}
                  </span>
                )}
                {!entry.version_from && entry.version_to && (
                  <span className="ml-2 text-sm text-muted-foreground">
                    → {entry.version_to}
                  </span>
                )}
                {entry.comment && (
                  <p className="text-sm mt-2">{entry.comment}</p>
                )}
              </div>
              <div className="text-right text-sm text-muted-foreground">
                <p>{formatDateTime(entry.changed_at)}</p>
                {entry.changed_by && <p>{t('changelog.by', { user: entry.changed_by })}</p>}
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

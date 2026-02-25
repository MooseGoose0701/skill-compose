"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Trash2 } from "lucide-react";
import { useTranslation } from "@/i18n/client";

interface DeleteSkillDialogProps {
  skillName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DeleteSkillDialog({
  skillName,
  open,
  onOpenChange,
}: DeleteSkillDialogProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { t } = useTranslation('skills');
  const [isDeleting, setIsDeleting] = React.useState(false);
  const [deleteError, setDeleteError] = React.useState<string | null>(null);

  const handleDeleteSkill = async () => {
    setIsDeleting(true);
    setDeleteError(null);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:62610';
      const response = await fetch(`${apiUrl}/api/v1/registry/skills/${skillName}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail || `Delete failed: ${response.statusText}`);
      }

      await queryClient.invalidateQueries({ queryKey: ["skills", "list"] });
      router.push('/skills');
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : t('delete.error'));
      setIsDeleting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Trash2 className="h-5 w-5 text-red-500" />
            {t('delete.title')}
          </DialogTitle>
          <DialogDescription>
            {t('delete.confirm', { name: skillName })}{' '}
            {t('delete.description')}
          </DialogDescription>
        </DialogHeader>
        {deleteError && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-md dark:bg-red-950 dark:border-red-800">
            <p className="text-red-600 text-sm dark:text-red-400">{deleteError}</p>
          </div>
        )}
        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isDeleting}>
            {t('delete.cancel')}
          </Button>
          <Button
            variant="destructive"
            onClick={handleDeleteSkill}
            disabled={isDeleting}
          >
            {isDeleting ? (
              <>
                <Spinner size="md" className="mr-2 text-white" />
                {t('delete.deleting')}
              </>
            ) : (
              t('delete.deleteButton')
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

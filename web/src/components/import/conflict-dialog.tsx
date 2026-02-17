"use client";

import { AlertTriangle, Copy } from "lucide-react";
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
import { useTranslation } from "@/i18n/client";

export interface ConflictInfo {
  skillName: string;
  existingVersion: string;
  source: "file" | "github" | "folder";
}

interface ConflictDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  conflictInfo: ConflictInfo | null;
  onCreateCopy: () => void;
  onCancel: () => void;
  isImporting: boolean;
}

export function ConflictDialog({
  open,
  onOpenChange,
  conflictInfo,
  onCreateCopy,
  onCancel,
  isImporting,
}: ConflictDialogProps) {
  const { t } = useTranslation("import");
  const { t: tc } = useTranslation("common");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-yellow-500" />
            {t("conflict.title")}
          </DialogTitle>
          <DialogDescription
            dangerouslySetInnerHTML={{
              __html: t("conflict.description", {
                name: conflictInfo?.skillName ?? "",
                version: conflictInfo?.existingVersion ?? "",
                interpolation: { escapeValue: false },
              }),
            }}
          />
        </DialogHeader>
        <div className="py-4">
          <p className="text-sm text-muted-foreground">{t("conflict.question")}</p>
        </div>
        <DialogFooter className="flex-col sm:flex-row gap-2">
          <Button
            variant="outline"
            onClick={onCancel}
            disabled={isImporting}
            className="sm:flex-1"
          >
            {tc("actions.cancel")}
          </Button>
          <Button onClick={onCreateCopy} disabled={isImporting} className="sm:flex-1">
            {isImporting ? (
              <>
                <Spinner size="md" className="mr-2 text-white" />
                {t("conflict.creating")}
              </>
            ) : (
              <>
                <Copy className="h-4 w-4 mr-2" />
                {t("conflict.createCopy")}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

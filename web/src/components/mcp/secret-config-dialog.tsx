"use client";

import React from "react";
import { Key, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { mcpApi } from "@/lib/api";
import { useTranslation } from "@/i18n/client";
import type { SecretStatus } from "@/lib/api";

interface SecretConfigDialogProps {
  serverName: string;
  keyName: string;
  status: SecretStatus;
  onSave: () => Promise<void> | void;
}

export function SecretConfigDialog({ serverName, keyName, status, onSave }: SecretConfigDialogProps) {
  const { t } = useTranslation("mcp");
  const { t: tc } = useTranslation("common");

  const [open, setOpen] = React.useState(false);
  const [value, setValue] = React.useState("");
  const [showValue, setShowValue] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim()) {
      setError(t("secrets.placeholder"));
      return;
    }

    setError(null);
    setIsSubmitting(true);

    try {
      await mcpApi.setSecret(serverName, keyName, value.trim());
      await onSave();
      setOpen(false);
      setValue("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("secrets.error"));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async () => {
    setIsSubmitting(true);
    try {
      await mcpApi.deleteSecret(serverName, keyName);
      await onSave();
      setOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("secrets.error"));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant={status.configured ? "outline" : "default"}
          size="sm"
          className="h-7 text-xs"
        >
          <Key className="h-3 w-3 mr-1" />
          {status.configured ? t("secrets.update") : t("secrets.configure")}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{t("secrets.title")}</DialogTitle>
            <DialogDescription>
              {t("secrets.description")} <code className="bg-muted px-1 rounded">{keyName}</code>
            </DialogDescription>
          </DialogHeader>

          <div className="py-4 space-y-4">
            {status.source === "env" && (
              <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-md">
                <p className="text-sm text-blue-600 dark:text-blue-400">
                  <strong>Info:</strong> {t("secrets.envFallbackInfo")}
                </p>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="api-key">{t("secrets.apiKey")}</Label>
              <div className="relative">
                <Input
                  id="api-key"
                  type={showValue ? "text" : "password"}
                  placeholder={t("secrets.placeholder")}
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  className="pr-10"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute right-0 top-0 h-full px-3"
                  onClick={() => setShowValue(!showValue)}
                >
                  {showValue ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                {t("secrets.savedTo")} <code>config/mcp-secrets.json</code>
              </p>
            </div>

            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>

          <DialogFooter className="gap-2">
            {status.configured && status.source === "secrets" && (
              <Button type="button" variant="destructive" onClick={handleDelete} disabled={isSubmitting}>
                {tc("actions.delete")}
              </Button>
            )}
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {tc("actions.cancel")}
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? tc("actions.processing") : tc("actions.save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

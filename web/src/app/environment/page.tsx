"use client";

import React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
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
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Terminal,
  Key,
  Eye,
  EyeOff,
  RefreshCw,
  Plus,
  Trash2,
  Pencil,
  FileText,
} from "lucide-react";
import { settingsApi } from "@/lib/api";
import type { EnvVariable, EnvConfigResponse } from "@/lib/api";
import { useTranslation } from "@/i18n/client";

function AddVariableDialog({ onAdd, t, tc }: { onAdd: () => void; t: (key: string, options?: Record<string, unknown>) => string; tc: (key: string) => string }) {
  const [open, setOpen] = React.useState(false);
  const [key, setKey] = React.useState("");
  const [value, setValue] = React.useState("");
  const [showValue, setShowValue] = React.useState(true);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const isSensitive = React.useMemo(() => {
    const patterns = ["key", "password", "secret", "token", "credential", "auth"];
    return patterns.some((p) => key.toLowerCase().includes(p));
  }, [key]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await settingsApi.createEnv(key.toUpperCase(), value);
      setOpen(false);
      setKey("");
      setValue("");
      onAdd();
    } catch (err) {
      setError(err instanceof Error ? err.message : t('add.error'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="h-4 w-4 mr-2" />
          {t('add.title')}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{t('add.title')}</DialogTitle>
            <DialogDescription>
              {t('env.description')}
            </DialogDescription>
          </DialogHeader>

          <div className="py-4 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="key">{t('add.key')}</Label>
              <Input
                id="key"
                placeholder={t('add.keyPlaceholder')}
                value={key}
                onChange={(e) => setKey(e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, ""))}
                className="font-mono"
              />
              <p className="text-xs text-muted-foreground">
                {t('varNameHelp')}
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="value">{t('add.value')}</Label>
              <div className="relative">
                <Input
                  id="value"
                  type={isSensitive && !showValue ? "password" : "text"}
                  placeholder={t('add.valuePlaceholder')}
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  className="font-mono pr-10"
                />
                {isSensitive && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="absolute right-0 top-0 h-full px-3"
                    onClick={() => setShowValue(!showValue)}
                  >
                    {showValue ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </Button>
                )}
              </div>
              {isSensitive && (
                <p className="text-xs text-yellow-600 dark:text-yellow-400">
                  {t('sensitiveWarning')}
                </p>
              )}
            </div>

            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {tc('actions.cancel')}
            </Button>
            <Button type="submit" disabled={isSubmitting || !key}>
              {isSubmitting ? t('add.adding') : tc('actions.create')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function EditVariableDialog({
  variable,
  onSave,
  t,
  tc,
}: {
  variable: EnvVariable;
  onSave: (key: string, value: string) => Promise<void>;
  t: (key: string, options?: Record<string, unknown>) => string;
  tc: (key: string) => string;
}) {
  const [open, setOpen] = React.useState(false);
  const [value, setValue] = React.useState("");
  const [showValue, setShowValue] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      // Don't pre-fill sensitive values that are masked
      if (variable.sensitive && variable.value.includes("...")) {
        setValue("");
      } else {
        setValue(variable.value);
      }
    }
  }, [open, variable]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await onSave(variable.key, value);
      setOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('edit.error'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon" className="h-8 w-8">
          <Pencil className="h-4 w-4" />
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{t('edit.title')} {variable.key}</DialogTitle>
            <DialogDescription>
              {t('env.description')}
            </DialogDescription>
          </DialogHeader>

          <div className="py-4 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="value">{t('add.value')}</Label>
              <div className="relative">
                <Input
                  id="value"
                  type={variable.sensitive && !showValue ? "password" : "text"}
                  placeholder={t('add.valuePlaceholder')}
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  className="font-mono pr-10"
                />
                {variable.sensitive && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="absolute right-0 top-0 h-full px-3"
                    onClick={() => setShowValue(!showValue)}
                  >
                    {showValue ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </Button>
                )}
              </div>
              {variable.sensitive && (
                <p className="text-xs text-muted-foreground">
                  {t('leaveEmptyToKeep')}
                </p>
              )}
            </div>

            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {tc('actions.cancel')}
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? t('edit.saving') : tc('actions.save')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function DeleteVariableDialog({
  variable,
  onDelete,
  t,
  tc,
}: {
  variable: EnvVariable;
  onDelete: (key: string) => Promise<void>;
  t: (key: string, options?: Record<string, unknown>) => string;
  tc: (key: string) => string;
}) {
  const [isDeleting, setIsDeleting] = React.useState(false);

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await onDelete(variable.key);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive hover:text-destructive">
          <Trash2 className="h-4 w-4" />
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t('delete.title')} {variable.key}?</AlertDialogTitle>
          <AlertDialogDescription>
            {t('delete.description')}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{tc('actions.cancel')}</AlertDialogCancel>
          <AlertDialogAction
            onClick={handleDelete}
            disabled={isDeleting}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {isDeleting ? t('delete.deleting') : tc('actions.delete')}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function VariableRow({
  variable,
  onSave,
  onDelete,
  t,
  tc,
}: {
  variable: EnvVariable;
  onSave: (key: string, value: string) => Promise<void>;
  onDelete: (key: string) => Promise<void>;
  t: (key: string, options?: Record<string, unknown>) => string;
  tc: (key: string) => string;
}) {
  return (
    <div className="flex items-center justify-between p-3 rounded-lg border bg-card hover:bg-muted/30 transition-colors">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <code className="text-sm font-mono font-medium">{variable.key}</code>
          {variable.sensitive && (
            <Badge variant="outline" className="text-xs">
              <Key className="h-3 w-3 mr-1" />
              {t('sensitive')}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2 mt-1">
          <code className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded truncate max-w-[400px]">
            {variable.value || <span className="italic">{tc('empty.noData')}</span>}
          </code>
        </div>
      </div>
      <div className="flex items-center gap-1">
        <EditVariableDialog variable={variable} onSave={onSave} t={t} tc={tc} />
        <DeleteVariableDialog variable={variable} onDelete={onDelete} t={t} tc={tc} />
      </div>
    </div>
  );
}

export default function EnvironmentPage() {
  const { t } = useTranslation('settings');
  const { t: tc } = useTranslation('common');
  const queryClient = useQueryClient();

  const { data, isLoading, error, refetch } = useQuery<EnvConfigResponse>({
    queryKey: ["env-config"],
    queryFn: () => settingsApi.getEnv(),
  });

  const handleSave = async (key: string, value: string) => {
    // Skip if sensitive field is empty (keep current value)
    const variable = data?.variables.find((v) => v.key === key);
    if (variable?.sensitive && !value) {
      return;
    }

    await settingsApi.updateEnv(key, value);
    await queryClient.invalidateQueries({ queryKey: ["env-config"] });
    await queryClient.invalidateQueries({ queryKey: ["models-providers"] });
  };

  const handleDelete = async (key: string) => {
    await settingsApi.deleteEnv(key);
    await queryClient.invalidateQueries({ queryKey: ["env-config"] });
    await queryClient.invalidateQueries({ queryKey: ["models-providers"] });
  };

  const handleAdd = async () => {
    await queryClient.invalidateQueries({ queryKey: ["env-config"] });
    await queryClient.invalidateQueries({ queryKey: ["models-providers"] });
  };

  const envVariables = data?.variables || [];
  // Sort sensitive variables first within each category
  const sortBySensitive = (a: EnvVariable, b: EnvVariable) => {
    if (a.sensitive && !b.sensitive) return -1;
    if (!a.sensitive && b.sensitive) return 1;
    return a.key.localeCompare(b.key);
  };
  const customVariables = envVariables.filter((v) => v.category === "custom").sort(sortBySensitive);
  const presetVariables = envVariables.filter((v) => v.category === "preset").sort(sortBySensitive);

  return (
    <div className="container max-w-4xl py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">{t('title')}</h1>
          <p className="text-muted-foreground mt-1">
            {t('description')}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => refetch()} disabled={isLoading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? "animate-spin" : ""}`} />
            {tc('actions.refresh')}
          </Button>
          <AddVariableDialog onAdd={handleAdd} t={t} tc={tc} />
        </div>
      </div>

      {/* Status Card */}
      <Card className="mb-6">
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Terminal className="h-4 w-4" />
            {t('configStatus')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-6">
            <div>
              <p className="text-2xl font-bold">{envVariables.length}</p>
              <p className="text-xs text-muted-foreground">{t('variablesInEnv')}</p>
            </div>
            {data?.env_file_path && (
              <>
                <div className="h-8 w-px bg-border" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-muted-foreground">{t('configFile')}</p>
                  <code className="text-xs bg-muted px-1 rounded truncate block">
                    {data.env_file_path}
                  </code>
                </div>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Custom Environment Variables */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            {t('customEnvVars')}
          </CardTitle>
          <CardDescription>
            {t('customEnvVarsDescription')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <div className="text-center py-12">
              <p className="text-destructive">{t('failedToLoad')}</p>
              <p className="text-sm text-muted-foreground mt-1">
                {t('apiServerCheck')}
              </p>
            </div>
          ) : customVariables.length === 0 ? (
            <div className="text-center py-8">
              <Terminal className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
              <p className="text-muted-foreground">{t('noEnvConfigured')}</p>
              <p className="text-sm text-muted-foreground mt-1">
                {t('noEnvConfiguredHelp')}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {customVariables.map((variable) => (
                <VariableRow
                  key={variable.key}
                  variable={variable}
                  onSave={handleSave}
                  onDelete={handleDelete}
                  t={t}
                  tc={tc}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Preset Environment Variables (API Keys) */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Key className="h-5 w-5" />
            {t('presetEnvVars')}
          </CardTitle>
          <CardDescription>
            {t('presetEnvVarsDescription')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : presetVariables.length === 0 ? (
            <div className="text-center py-8">
              <Key className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
              <p className="text-muted-foreground">{t('noPresetConfigured')}</p>
            </div>
          ) : (
            <div className="space-y-2">
              {presetVariables.map((variable) => (
                <VariableRow
                  key={variable.key}
                  variable={variable}
                  onSave={handleSave}
                  onDelete={handleDelete}
                  t={t}
                  tc={tc}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

    </div>
  );
}

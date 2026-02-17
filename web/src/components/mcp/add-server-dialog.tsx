"use client";

import React from "react";
import { Plus, Minus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
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
import { toast } from "sonner";
import { useTranslation } from "@/i18n/client";

interface AddServerDialogProps {
  onAdd: () => void;
}

export function AddServerDialog({ onAdd }: AddServerDialogProps) {
  const { t } = useTranslation("mcp");
  const { t: tc } = useTranslation("common");

  const [open, setOpen] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const [formData, setFormData] = React.useState({
    name: "",
    display_name: "",
    description: "",
    command: "uvx",
    default_enabled: false,
  });
  const [argRows, setArgRows] = React.useState<string[]>([""]);
  const [envRows, setEnvRows] = React.useState<{ key: string; value: string }[]>([{ key: "", value: "" }]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const args = argRows.map((s) => s.trim()).filter((s) => s.length > 0);

      const env: Record<string, string> = {};
      envRows.forEach(({ key, value }) => {
        const k = key.trim();
        if (k) env[k] = value.trim();
      });

      const serverName = formData.name;

      await mcpApi.createServer({
        name: serverName,
        display_name: formData.display_name,
        description: formData.description,
        command: formData.command,
        args,
        env,
        default_enabled: formData.default_enabled,
        tools: [],
      });

      setOpen(false);
      setFormData({ name: "", display_name: "", description: "", command: "uvx", default_enabled: false });
      setArgRows([""]);
      setEnvRows([{ key: "", value: "" }]);
      onAdd();

      // Fire-and-forget: auto-discover tools for the new server
      mcpApi
        .discoverTools(serverName)
        .then((result) => {
          if (result.success && result.tools_count > 0) {
            toast.success(t("discover.autoDiscovered", { count: result.tools_count }));
            onAdd();
          }
        })
        .catch(() => {
          // Discovery failure is non-fatal; server was already created
        });
    } catch (err) {
      setError(err instanceof Error ? err.message : t("create.error"));
    } finally {
      setIsSubmitting(false);
    }
  };

  const updateArg = (index: number, value: string) => {
    const updated = [...argRows];
    updated[index] = value;
    setArgRows(updated);
  };
  const addArg = () => setArgRows([...argRows, ""]);
  const removeArg = (index: number) => {
    if (argRows.length <= 1) {
      setArgRows([""]);
      return;
    }
    setArgRows(argRows.filter((_, i) => i !== index));
  };

  const updateEnv = (index: number, field: "key" | "value", val: string) => {
    const updated = [...envRows];
    updated[index] = { ...updated[index], [field]: val };
    setEnvRows(updated);
  };
  const addEnv = () => setEnvRows([...envRows, { key: "", value: "" }]);
  const removeEnv = (index: number) => {
    if (envRows.length <= 1) {
      setEnvRows([{ key: "", value: "" }]);
      return;
    }
    setEnvRows(envRows.filter((_, i) => i !== index));
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="h-4 w-4 mr-2" />
          {t("addServer.addServer")}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{t("addServer.title")}</DialogTitle>
            <DialogDescription>{t("addServer.description")}</DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="name">{t("addServer.serverId")}</Label>
                <Input
                  id="name"
                  placeholder={t("addServer.serverIdPlaceholder")}
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                />
                <p className="text-xs text-muted-foreground">{t("addServer.serverIdHelp")}</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="display_name">{t("addServer.displayName")}</Label>
                <Input
                  id="display_name"
                  placeholder={t("addServer.displayNamePlaceholder")}
                  value={formData.display_name}
                  onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">{t("addServer.description2")}</Label>
              <Textarea
                id="description"
                placeholder={t("addServer.descriptionPlaceholder")}
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={2}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="command">{t("addServer.command")}</Label>
              <Input
                id="command"
                placeholder={t("addServer.commandPlaceholder")}
                value={formData.command}
                onChange={(e) => setFormData({ ...formData, command: e.target.value })}
                required
              />
              <p className="text-xs text-muted-foreground">{t("addServer.commandHelp")}</p>
            </div>

            {/* Dynamic Args rows */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>{t("addServer.arguments")}</Label>
                <Button type="button" variant="ghost" size="sm" className="h-7 text-xs" onClick={addArg}>
                  <Plus className="h-3 w-3 mr-1" />
                  {tc("actions.add")}
                </Button>
              </div>
              <div className="space-y-2">
                {argRows.map((arg, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <Input
                      placeholder={t("addServer.argumentsPlaceholder")}
                      value={arg}
                      onChange={(e) => updateArg(i, e.target.value)}
                      className="flex-1"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 shrink-0 text-muted-foreground hover:text-destructive"
                      onClick={() => removeArg(i)}
                    >
                      <Minus className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">{t("addServer.argumentsHelp")}</p>
            </div>

            {/* Dynamic Env rows */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>{t("addServer.envVars")}</Label>
                <Button type="button" variant="ghost" size="sm" className="h-7 text-xs" onClick={addEnv}>
                  <Plus className="h-3 w-3 mr-1" />
                  {t("create.envAdd")}
                </Button>
              </div>
              <div className="space-y-2">
                {envRows.map((row, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <Input
                      placeholder={t("create.envKey")}
                      value={row.key}
                      onChange={(e) => updateEnv(i, "key", e.target.value)}
                      className="flex-1"
                    />
                    <span className="text-muted-foreground">=</span>
                    <Input
                      placeholder={t("create.envValue")}
                      value={row.value}
                      onChange={(e) => updateEnv(i, "value", e.target.value)}
                      className="flex-1"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 shrink-0 text-muted-foreground hover:text-destructive"
                      onClick={() => removeEnv(i)}
                    >
                      <Minus className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">{t("addServer.envVarsHelp")}</p>
            </div>

            <div className="flex items-center space-x-2">
              <Switch
                id="default_enabled"
                checked={formData.default_enabled}
                onCheckedChange={(checked) => setFormData({ ...formData, default_enabled: checked })}
              />
              <Label htmlFor="default_enabled">{t("addServer.enableByDefault")}</Label>
            </div>

            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {tc("actions.cancel")}
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? t("addServer.adding") : t("addServer.addServer")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

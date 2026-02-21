"use client";

import React from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { CodeEditor } from "@/components/editor/code-editor";
import { mcpApi } from "@/lib/api";
import { toast } from "sonner";
import { useTranslation } from "@/i18n/client";
import { useTheme } from "next-themes";

interface AddServerDialogProps {
  onAdd: () => void;
}

const DEFAULT_TEMPLATE = JSON.stringify(
  {
    "server-name": {
      command: "npx",
      args: ["package-name"],
    },
  },
  null,
  2
);

function parseServerConfig(jsonStr: string, t: (key: string) => string) {
  let parsed: unknown;
  try {
    parsed = JSON.parse(jsonStr);
  } catch {
    throw new Error(t("addServer.invalidJson"));
  }

  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new Error(t("addServer.invalidJson"));
  }

  let obj = parsed as Record<string, unknown>;

  // Auto-unwrap "mcpServers" wrapper (common README format)
  if (obj.mcpServers && typeof obj.mcpServers === "object" && Object.keys(obj).length === 1) {
    obj = obj.mcpServers as Record<string, unknown>;
  }

  const keys = Object.keys(obj);
  if (keys.length !== 1) {
    throw new Error(t("addServer.singleServerRequired"));
  }

  const name = keys[0];
  const config = obj[name] as Record<string, unknown> | undefined;

  if (!config || typeof config !== "object" || !config.command) {
    throw new Error(t("addServer.commandRequired"));
  }

  return {
    name,
    display_name: (config.name as string) || name,
    description: (config.description as string) || "",
    command: config.command as string,
    args: (config.args as string[]) || [],
    env: (config.env as Record<string, string>) || {},
    default_enabled: (config.defaultEnabled as boolean) || false,
    tools: [],
  };
}

export function AddServerDialog({ onAdd }: AddServerDialogProps) {
  const { t } = useTranslation("mcp");
  const { t: tc } = useTranslation("common");
  const { resolvedTheme } = useTheme();

  const [open, setOpen] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [jsonValue, setJsonValue] = React.useState(DEFAULT_TEMPLATE);

  const handleSubmit = async () => {
    setError(null);
    setIsSubmitting(true);

    try {
      const serverConfig = parseServerConfig(jsonValue, t);

      await mcpApi.createServer(serverConfig);

      const serverName = serverConfig.name;
      setOpen(false);
      setJsonValue(DEFAULT_TEMPLATE);
      setError(null);
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

  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen) => {
        setOpen(isOpen);
        if (!isOpen) {
          setError(null);
          setJsonValue(DEFAULT_TEMPLATE);
        }
      }}
    >
      <DialogTrigger asChild>
        <Button>
          <Plus className="h-4 w-4 mr-2" />
          {t("addServer.addServer")}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{t("addServer.title")}</DialogTitle>
          <DialogDescription>{t("addServer.description")}</DialogDescription>
        </DialogHeader>

        <div className="py-2">
          <CodeEditor
            value={jsonValue}
            onChange={setJsonValue}
            language="json"
            height="260px"
            theme={resolvedTheme === "dark" ? "vs-dark" : "light"}
            minimap={false}
          />

          {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            {tc("actions.cancel")}
          </Button>
          <Button onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? t("addServer.adding") : t("addServer.addServer")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

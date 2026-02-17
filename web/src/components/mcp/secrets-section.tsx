"use client";

import { Check, X, Key } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useTranslation } from "@/i18n/client";
import type { MCPServerInfo } from "@/lib/api";
import { SecretConfigDialog } from "./secret-config-dialog";

interface SecretsSectionProps {
  server: MCPServerInfo;
  onUpdate: () => Promise<void> | void;
}

export function SecretsSection({ server, onUpdate }: SecretsSectionProps) {
  const { t } = useTranslation("mcp");

  if (!server.required_env_vars || server.required_env_vars.length === 0) {
    return null;
  }

  return (
    <div className="mt-4 pt-4 border-t">
      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
        <Key className="h-3 w-3 inline mr-1" />
        {t("requiredApiKeys")}
      </p>
      <div className="space-y-2">
        {server.required_env_vars.map((keyName) => {
          const status = server.secrets_status?.[keyName] || { configured: false, source: "none" };
          return (
            <div key={keyName} className="flex items-center justify-between p-2 rounded border bg-muted/20">
              <div className="flex items-center gap-2">
                <code className="text-xs font-mono">{keyName}</code>
                {status.configured ? (
                  <Badge variant="outline-success" className="text-xs">
                    <Check className="h-3 w-3 mr-1" />
                    {status.source === "env" ? t("fromEnv") : t("configured")}
                  </Badge>
                ) : (
                  <Badge variant="outline-error" className="text-xs">
                    <X className="h-3 w-3 mr-1" />
                    {t("notSet")}
                  </Badge>
                )}
              </div>
              <SecretConfigDialog serverName={server.name} keyName={keyName} status={status} onSave={onUpdate} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

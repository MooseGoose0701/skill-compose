"use client";

import React from "react";
import { Plug, Trash2, Lock, Key, RefreshCw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { mcpApi } from "@/lib/api";
import { toast } from "sonner";
import { useTranslation } from "@/i18n/client";
import type { MCPServerInfo } from "@/lib/api";
import { SecretsSection } from "./secrets-section";
import { ToolsList } from "./tools-list";

interface MCPServerCardProps {
  server: MCPServerInfo;
  onDelete: (name: string) => void;
  onUpdate: () => Promise<void> | void;
  isBuiltIn: boolean;
}

export function MCPServerCard({ server, onDelete, onUpdate, isBuiltIn }: MCPServerCardProps) {
  const { t } = useTranslation("mcp");
  const { t: tc } = useTranslation("common");
  const [isDiscovering, setIsDiscovering] = React.useState(false);

  const hasUnconfiguredKeys = server.required_env_vars?.some(
    (key) => !server.secrets_status?.[key]?.configured
  );

  const handleDiscover = async () => {
    setIsDiscovering(true);
    try {
      const result = await mcpApi.discoverTools(server.name);
      if (result.success) {
        toast.success(t("discover.success", { count: result.tools_count }));
        await onUpdate();
      } else {
        toast.error(result.error || t("discover.failed"));
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("discover.failed"));
    } finally {
      setIsDiscovering(false);
    }
  };

  return (
    <Card className={hasUnconfiguredKeys ? "border-yellow-500/50" : ""}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-md ${hasUnconfiguredKeys ? "bg-yellow-500/10 text-yellow-500" : "bg-purple-500/10 text-purple-500"}`}>
              <Plug className="h-5 w-5" />
            </div>
            <div>
              <CardTitle className="text-base">{server.display_name}</CardTitle>
              <p className="text-xs text-muted-foreground mt-0.5">{server.name}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {hasUnconfiguredKeys && (
              <Badge variant="outline-warning" className="text-xs">
                <Key className="h-3 w-3 mr-1" />
                {t("needsConfig")}
              </Badge>
            )}
            {isBuiltIn && (
              <Badge variant="outline" className="text-xs">
                <Lock className="h-3 w-3 mr-1" />
                {t("builtIn")}
              </Badge>
            )}
            {server.default_enabled && (
              <Badge variant="secondary" className="text-xs">
                {t("defaultEnabled")}
              </Badge>
            )}
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={handleDiscover}
              disabled={isDiscovering}
              title={server.tools.length > 0 ? t("discover.refreshTools") : t("discover.discoverTools")}
            >
              <RefreshCw className={`h-4 w-4 ${isDiscovering ? "animate-spin" : ""}`} />
            </Button>
            {isBuiltIn ? (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-muted-foreground cursor-not-allowed"
                disabled
                title={t("delete.cannotDelete")}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            ) : (
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive hover:text-destructive">
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>{t("delete.title")}</AlertDialogTitle>
                    <AlertDialogDescription>
                      {t("delete.confirm", { name: server.display_name })}
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>{tc("actions.cancel")}</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={() => onDelete(server.name)}
                      className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    >
                      {tc("actions.delete")}
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <p className="text-sm text-muted-foreground mb-4">{server.description}</p>

        <SecretsSection server={server} onUpdate={onUpdate} />

        {server.tools.length > 0 ? (
          <ToolsList tools={server.tools} hasSecrets={!!server.required_env_vars?.length} />
        ) : (
          <div className={`text-sm text-muted-foreground italic ${server.required_env_vars?.length ? "mt-4 pt-4 border-t" : ""}`}>
            {t("discover.noTools")}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

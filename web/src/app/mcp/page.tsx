"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useMCPServers } from "@/hooks/use-mcp";
import { mcpApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Plug } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { useTranslation } from "@/i18n/client";
import { MCPServerCard } from "@/components/mcp/mcp-server-card";
import { AddServerDialog } from "@/components/mcp/add-server-dialog";

const BUILTIN_MCP_SERVERS = ["time", "tavily", "git"];

export default function MCPPage() {
  const { t } = useTranslation("mcp");
  const { t: tc } = useTranslation("common");
  const queryClient = useQueryClient();
  const { data: mcpData, isLoading } = useMCPServers();

  const handleDelete = async (name: string) => {
    try {
      await mcpApi.deleteServer(name);
      queryClient.invalidateQueries({ queryKey: ["mcp-servers"] });
    } catch (err) {
      console.error("Failed to delete server:", err);
    }
  };

  const handleAdd = async () => {
    await queryClient.invalidateQueries({ queryKey: ["mcp-servers"] });
  };

  return (
    <div className="container max-w-6xl py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">{t("title")}</h1>
          <p className="text-muted-foreground mt-1">{t("description")}</p>
        </div>
        <AddServerDialog onAdd={handleAdd} />
      </div>

      {/* Content */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plug className="h-5 w-5" />
            {t("availableServers")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <p className="text-muted-foreground">{tc("actions.loading")}</p>
            </div>
          ) : !mcpData || mcpData.servers.length === 0 ? (
            <EmptyState icon={Plug} title={t("list.empty")} description={t("list.emptyDescription")} />
          ) : (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">{t("mcpInfo")}</p>
                <Badge variant="outline">{t("serversCount", { count: mcpData.servers.length })}</Badge>
              </div>

              {(() => {
                const defaultServers = mcpData.servers.filter((s) => s.default_enabled);
                const optionalServers = mcpData.servers.filter((s) => !s.default_enabled);

                return (
                  <>
                    {defaultServers.length > 0 && (
                      <div>
                        <h3 className="font-medium mb-3 flex items-center gap-2">
                          <Badge variant="secondary" className="text-xs">
                            {t("defaultEnabled")}
                          </Badge>
                          <span className="text-sm text-muted-foreground">({defaultServers.length})</span>
                        </h3>
                        <div className="grid gap-4 md:grid-cols-2">
                          {defaultServers.map((server) => (
                            <MCPServerCard
                              key={server.name}
                              server={server}
                              onDelete={handleDelete}
                              onUpdate={handleAdd}
                              isBuiltIn={BUILTIN_MCP_SERVERS.includes(server.name)}
                            />
                          ))}
                        </div>
                      </div>
                    )}

                    {optionalServers.length > 0 && (
                      <div>
                        <h3 className="font-medium mb-3 flex items-center gap-2">
                          {t("optionalServers")}
                          <span className="text-sm text-muted-foreground">({optionalServers.length})</span>
                        </h3>
                        <div className="grid gap-4 md:grid-cols-2">
                          {optionalServers.map((server) => (
                            <MCPServerCard
                              key={server.name}
                              server={server}
                              onDelete={handleDelete}
                              onUpdate={handleAdd}
                              isBuiltIn={BUILTIN_MCP_SERVERS.includes(server.name)}
                            />
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                );
              })()}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

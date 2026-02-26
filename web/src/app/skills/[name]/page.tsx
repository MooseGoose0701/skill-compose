"use client";

import React from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { skillsApi, versionsApi, changelogsApi, resourcesApi, transferApi, type SkillResources } from "@/lib/api";
import { skillKeys } from "@/hooks/use-skills";
import { useChatPanel } from "@/components/chat/chat-provider";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { ArrowLeft, Download, Trash2, MoreHorizontal, Loader2, Upload } from "lucide-react";
import { toast } from "sonner";
import { useTranslation } from "@/i18n/client";

import { SkillTypeBadge } from "@/components/skill/skill-type-badge";
import { SkillOverview } from "@/components/skill/skill-overview";
import { ChangelogList } from "@/components/skill/changelog-list";
import { ResourcesList } from "@/components/skill/resources-list";
import { VersionTimeline } from "@/components/skill/version-timeline";
import { EvolveSkillModal } from "@/components/skill/evolve-trace-modal";
import { DeleteSkillDialog } from "@/components/skill/delete-skill-dialog";
import { UpdateFromSourceModal } from "@/components/skill/update-from-source-modal";
import { FilesystemSyncDialog } from "@/components/skill/filesystem-sync-dialog";

export default function SkillDetailPage() {
  const { t } = useTranslation("skills");
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const skillName = params.name as string;
  const chatPanel = useChatPanel();

  const initialTab = searchParams.get("tab") || "overview";

  // Modal state
  const [evolveModalOpen, setEvolveModalOpen] = React.useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false);
  const [isExporting, setIsExporting] = React.useState(false);
  const [updateSourceModalOpen, setUpdateSourceModalOpen] = React.useState(false);

  // Filesystem sync state
  const [syncDialogOpen, setSyncDialogOpen] = React.useState(false);
  const [syncResult, setSyncResult] = React.useState<{
    old_version: string;
    new_version: string;
    changes_summary?: string;
  } | null>(null);
  const syncingRef = React.useRef(false);

  // Protected skills that cannot be deleted
  const PROTECTED_SKILLS = ['skill-creator', 'skill-updater', 'skill-evolver'];
  const isProtectedSkill = PROTECTED_SKILLS.includes(skillName);

  // Fetch skill
  const {
    data: skill,
    isLoading: skillLoading,
    error: skillError,
  } = useQuery({
    queryKey: ["skill", skillName],
    queryFn: () => skillsApi.get(skillName),
    retry: (failureCount, error) => {
      if (error && 'status' in error && (error as { status: number }).status === 404) {
        return false;
      }
      return failureCount < 2;
    },
  });

  // Fetch versions
  const { data: versionsData, isLoading: versionsLoading } = useQuery({
    queryKey: ["versions", skillName],
    queryFn: () => versionsApi.list(skillName),
    enabled: !!skill,
  });

  // Fetch current version content
  const { data: currentVersion } = useQuery({
    queryKey: ["version", skillName, skill?.current_version],
    queryFn: () => versionsApi.get(skillName, skill!.current_version!),
    enabled: !!skill?.current_version,
  });

  // Fetch changelogs
  const { data: changelogsData, isLoading: changelogsLoading } = useQuery({
    queryKey: ["changelogs", skillName],
    queryFn: () => changelogsApi.list(skillName),
    enabled: !!skill,
  });

  // Fetch resources: try filesystem first, fallback to database version files
  const { data: skillWithResources, isLoading: resourcesLoading } = useQuery({
    queryKey: ["resources", skillName, skill?.current_version],
    queryFn: async (): Promise<{ resources: SkillResources }> => {
      // Try filesystem first
      try {
        return await resourcesApi.get(skillName);
      } catch (fsErr: unknown) {
        // Filesystem 404 → skill only exists in database, build resources from version files
        const err = fsErr as Record<string, unknown> | null;
        if (err && typeof err === 'object' && 'status' in err && err.status === 404 && skill?.current_version) {
          const versionFiles = await versionsApi.getVersionFiles(skillName, skill.current_version);
          const resources: SkillResources = { scripts: [], references: [], assets: [], other: [] };
          for (const f of versionFiles.files) {
            if (f.file_type === 'script') {
              const filename = f.file_path.replace(/^scripts\//, '');
              resources.scripts.push(filename);
            } else if (f.file_type === 'reference') {
              const filename = f.file_path.replace(/^references\//, '');
              resources.references.push(filename);
            } else if (f.file_type === 'asset') {
              const filename = f.file_path.replace(/^assets\//, '');
              resources.assets.push(filename);
            } else {
              // Include files in other directories (e.g., rules/, etc.)
              resources.other.push(f.file_path);
            }
          }
          return { resources };
        }
        throw fsErr;
      }
    },
    enabled: !!skill,
    retry: false,
  });

  const refreshAllData = React.useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["skill", skillName] });
    queryClient.invalidateQueries({ queryKey: ["versions", skillName] });
    queryClient.invalidateQueries({ queryKey: ["changelogs", skillName] });
    queryClient.invalidateQueries({ queryKey: skillKeys.githubStatus() });
    queryClient.invalidateQueries({ queryKey: ["resources", skillName] });
    queryClient.invalidateQueries({ queryKey: ["version", skillName] });
  }, [queryClient, skillName]);

  // Check filesystem sync — called on page load and tab switch
  const checkFilesystemSync = React.useCallback(() => {
    if (!skill || syncingRef.current) return;
    syncingRef.current = true;

    skillsApi.syncFilesystem(skillName).then((result) => {
      if (result.synced && result.old_version && result.new_version) {
        setSyncResult({
          old_version: result.old_version,
          new_version: result.new_version,
          changes_summary: result.changes_summary,
        });
        setSyncDialogOpen(true);
        refreshAllData();
      }
    }).catch(() => {
      // Silently ignore sync errors (e.g. imported-only skills)
    }).finally(() => {
      syncingRef.current = false;
    });
  }, [skill, skillName, refreshAllData]);

  // Trigger sync on initial page load
  React.useEffect(() => {
    checkFilesystemSync();
  }, [checkFilesystemSync]);

  if (skillLoading) {
    return (
      <div className="container mx-auto py-8">
        <p className="text-muted-foreground">{t("loading.skill")}</p>
      </div>
    );
  }

  if (skillError || !skill) {
    return (
      <div className="container mx-auto py-8">
        <Card>
          <CardContent className="p-6 text-center">
            <p className="text-red-500">
              {t("loading.failedToLoad", { error: skillError?.message || "Not found" })}
            </p>
            <Button className="mt-4" onClick={() => router.push("/skills")}>
              {t("actions.backToSkills")}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold">{skill.name}</h1>
            <SkillTypeBadge skillType={skill.skill_type} />
          </div>
          {skill.current_version && (
            <p className="text-muted-foreground mt-1">
              v{skill.current_version}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => router.push("/skills")}
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            {t("actions.back")}
          </Button>
          <Button
            onClick={() => chatPanel.open([skillName])}
          >
            {t("actions.testWithChat")}
          </Button>
          <Button
            variant="outline"
            onClick={() => setEvolveModalOpen(true)}
          >
            {t("actions.evolve")}
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="icon">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                disabled={isExporting}
                onSelect={async () => {
                  setIsExporting(true);
                  try {
                    const blob = await transferApi.exportSkill(skillName);
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `${skillName}.skill`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                    toast.success(t("export.success"));
                  } catch {
                    toast.error(t("export.error"));
                  } finally {
                    setIsExporting(false);
                  }
                }}
              >
                {isExporting ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Download className="mr-2 h-4 w-4" />
                )}
                {t("actions.export")}
              </DropdownMenuItem>
              <DropdownMenuItem
                onSelect={() => setUpdateSourceModalOpen(true)}
              >
                <Upload className="mr-2 h-4 w-4" />
                {t("actions.updateFromSource")}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                disabled={isProtectedSkill}
                className="text-destructive focus:text-destructive"
                onSelect={() => setDeleteDialogOpen(true)}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                {t("actions.delete")}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue={initialTab} className="space-y-4" onValueChange={() => checkFilesystemSync()}>
        <TabsList>
          <TabsTrigger value="overview">{t("tabs.overview")}</TabsTrigger>
          <TabsTrigger value="resources">{t("tabs.resources")}</TabsTrigger>
          <TabsTrigger value="versions">
            {t("tabs.versions", { count: versionsData?.total || 0 })}
          </TabsTrigger>
          <TabsTrigger value="changelog">{t("tabs.changelog")}</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>{t("cards.skillInformation")}</CardTitle>
            </CardHeader>
            <CardContent>
              <SkillOverview skill={skill} />
            </CardContent>
          </Card>

        </TabsContent>

        <TabsContent value="resources">
          <Card>
            <CardHeader>
              <CardTitle>{t("cards.skillFiles")}</CardTitle>
            </CardHeader>
            <CardContent>
              <ResourcesList
                skillName={skillName}
                resources={skillWithResources?.resources || null}
                isLoading={resourcesLoading}
                currentVersion={currentVersion}
                onVersionCreated={refreshAllData}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="versions">
          <Card>
            <CardHeader>
              <CardTitle>{t("cards.versionHistory")}</CardTitle>
            </CardHeader>
            <CardContent>
              <VersionTimeline
                skillName={skillName}
                versions={versionsData?.versions || []}
                isLoading={versionsLoading}
                currentVersion={skill.current_version || undefined}
                onVersionSwitch={refreshAllData}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="changelog">
          <Card>
            <CardHeader>
              <CardTitle>{t("cards.activityLog")}</CardTitle>
            </CardHeader>
            <CardContent>
              <ChangelogList
                changelogs={changelogsData?.changelogs || []}
                isLoading={changelogsLoading}
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Evolve Skill Modal */}
      <EvolveSkillModal
        skillName={skillName}
        open={evolveModalOpen}
        onOpenChange={setEvolveModalOpen}
        onComplete={refreshAllData}
      />

      {/* Update From Source Modal */}
      <UpdateFromSourceModal
        skillName={skillName}
        open={updateSourceModalOpen}
        onOpenChange={setUpdateSourceModalOpen}
        onComplete={refreshAllData}
      />

      {/* Delete Confirmation Dialog */}
      <DeleteSkillDialog
        skillName={skillName}
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
      />

      {/* Filesystem Sync Dialog */}
      {syncResult && (
        <FilesystemSyncDialog
          open={syncDialogOpen}
          onOpenChange={setSyncDialogOpen}
          oldVersion={syncResult.old_version}
          newVersion={syncResult.new_version}
          changesSummary={syncResult.changes_summary}
        />
      )}
    </div>
  );
}

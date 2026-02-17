"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Upload, ArrowLeft, Github, Folder } from "lucide-react";
import { useTranslation } from "@/i18n/client";
import { ConflictDialog } from "@/components/import/conflict-dialog";
import type { ConflictInfo } from "@/components/import/conflict-dialog";
import { GitHubImportTab } from "@/components/import/github-import-tab";
import { FileImportTab } from "@/components/import/file-import-tab";
import { FolderImportTab } from "@/components/import/folder-import-tab";

export default function ImportPage() {
  const router = useRouter();
  const { t } = useTranslation("import");
  const { t: tc } = useTranslation("common");

  const [activeTab, setActiveTab] = React.useState("github");

  // Shared conflict dialog state
  const [conflictDialogOpen, setConflictDialogOpen] = React.useState(false);
  const [conflictInfo, setConflictInfo] = React.useState<ConflictInfo | null>(null);
  const [isConflictImporting, setIsConflictImporting] = React.useState(false);
  const pendingImportRef = React.useRef<((action?: string) => Promise<void>) | null>(null);

  const handleConflict = (info: ConflictInfo) => {
    setConflictInfo(info);
    setConflictDialogOpen(true);
  };

  const handleResolveConflict = (doImport: (action?: string) => Promise<void>) => {
    pendingImportRef.current = doImport;
  };

  const handleCreateCopy = async () => {
    if (!pendingImportRef.current) return;
    setIsConflictImporting(true);
    try {
      await pendingImportRef.current("copy");
    } finally {
      setIsConflictImporting(false);
      setConflictDialogOpen(false);
      setConflictInfo(null);
      pendingImportRef.current = null;
    }
  };

  const handleCancelConflict = () => {
    setConflictDialogOpen(false);
    setConflictInfo(null);
    pendingImportRef.current = null;
  };

  return (
    <div className="container mx-auto py-8 max-w-2xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">{t("title")}</h1>
          <p className="text-muted-foreground mt-1">{t("description")}</p>
        </div>
        <Button variant="outline" onClick={() => router.push("/skills")}>
          <ArrowLeft className="h-4 w-4 mr-1" />
          {t("backToSkills")}
        </Button>
      </div>

      {/* Import Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-3 mb-4">
          <TabsTrigger value="github" className="flex items-center gap-2">
            <Github className="h-4 w-4" />
            {t("tabs.github")}
          </TabsTrigger>
          <TabsTrigger value="file" className="flex items-center gap-2">
            <Upload className="h-4 w-4" />
            {t("tabs.file")}
          </TabsTrigger>
          <TabsTrigger value="folder" className="flex items-center gap-2">
            <Folder className="h-4 w-4" />
            {t("tabs.folder")}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="github">
          <GitHubImportTab onConflict={handleConflict} onResolveConflict={handleResolveConflict} />
        </TabsContent>
        <TabsContent value="file">
          <FileImportTab onConflict={handleConflict} onResolveConflict={handleResolveConflict} />
        </TabsContent>
        <TabsContent value="folder">
          <FolderImportTab onConflict={handleConflict} onResolveConflict={handleResolveConflict} />
        </TabsContent>
      </Tabs>

      {/* Info Card */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-base">{t("about.title")}</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-2">
          <p dangerouslySetInnerHTML={{ __html: t("about.description") }} />
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li dangerouslySetInnerHTML={{ __html: t("about.skillMd") }} />
            <li dangerouslySetInnerHTML={{ __html: t("about.scripts") }} />
            <li dangerouslySetInnerHTML={{ __html: t("about.references") }} />
            <li dangerouslySetInnerHTML={{ __html: t("about.assets") }} />
            <li dangerouslySetInnerHTML={{ __html: t("about.schema") }} />
          </ul>
          <p className="pt-2">{t("about.conflictNote")}</p>
        </CardContent>
      </Card>

      {/* Shared Conflict Dialog */}
      <ConflictDialog
        open={conflictDialogOpen}
        onOpenChange={setConflictDialogOpen}
        conflictInfo={conflictInfo}
        onCreateCopy={handleCreateCopy}
        onCancel={handleCancelConflict}
        isImporting={isConflictImporting}
      />
    </div>
  );
}

"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/badge";
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
import { GitCompare, Clock, User, Maximize2, Minimize2, ArrowRightLeft, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { DiffViewer } from "@/components/diff/diff-viewer";
import { versionsApi } from "@/lib/api";
import { useDeleteVersion } from "@/hooks/use-skills";
import { useTranslation } from "@/i18n/client";
import { formatDateTime, getLanguageFromFilename } from "@/lib/formatters";
import type { SkillVersion } from "@/types/skill";

interface VersionFile {
  file_path: string;
  file_type: string;
  size_bytes?: number;
  content_hash?: string;
}

interface VersionTimelineProps {
  skillName: string;
  versions: SkillVersion[];
  isLoading: boolean;
  currentVersion?: string;
  onVersionSwitch?: () => void;
}

export function VersionTimeline({
  skillName,
  versions,
  isLoading,
  currentVersion,
  onVersionSwitch,
}: VersionTimelineProps) {
  const router = useRouter();
  const [compareFrom, setCompareFrom] = React.useState<string | null>(null);
  const [compareTo, setCompareTo] = React.useState<string | null>(null);
  const [diffData, setDiffData] = React.useState<{
    oldContent: string;
    newContent: string;
    diff: string;
  } | null>(null);
  const [diffLoading, setDiffLoading] = React.useState(false);
  const [diffModalOpen, setDiffModalOpen] = React.useState(false);
  const [splitView, setSplitView] = React.useState(true);
  const [viewModalOpen, setViewModalOpen] = React.useState(false);
  const [viewingVersion, setViewingVersion] = React.useState<SkillVersion | null>(null);
  const [viewLoading, setViewLoading] = React.useState(false);

  const [versionFiles, setVersionFiles] = React.useState<VersionFile[]>([]);
  const [selectedFile, setSelectedFile] = React.useState<string>("SKILL.md");
  const [fileContent, setFileContent] = React.useState<string | null>(null);
  const [fileLoading, setFileLoading] = React.useState(false);

  const [diffFilePath, setDiffFilePath] = React.useState<string>("SKILL.md");
  const [diffFiles, setDiffFiles] = React.useState<VersionFile[]>([]);
  const [isFullscreen, setIsFullscreen] = React.useState(false);

  const [switching, setSwitching] = React.useState(false);
  const [switchTarget, setSwitchTarget] = React.useState<string | null>(null);
  const [switchConfirmOpen, setSwitchConfirmOpen] = React.useState(false);

  const [deleteTarget, setDeleteTarget] = React.useState<string | null>(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = React.useState(false);
  const deleteVersionMutation = useDeleteVersion(skillName);
  const { t } = useTranslation("skills");

  const handleViewVersion = async (version: SkillVersion) => {
    setViewLoading(true);
    setViewModalOpen(true);
    setSelectedFile("SKILL.md");
    setFileContent(null);
    setVersionFiles([]);
    try {
      const fullVersion = await versionsApi.get(skillName, version.version);
      setViewingVersion(fullVersion);
      setFileContent(fullVersion.skill_md || null);

      try {
        const filesData = await versionsApi.getVersionFiles(skillName, version.version);
        setVersionFiles(filesData.files || []);
      } catch {
        setVersionFiles([]);
      }
    } catch (err) {
      console.error("Failed to load version:", err);
    } finally {
      setViewLoading(false);
    }
  };

  const handleSelectFile = async (filePath: string) => {
    if (!viewingVersion) return;
    setSelectedFile(filePath);

    if (filePath === "SKILL.md") {
      setFileContent(viewingVersion.skill_md || null);
      return;
    }

    setFileLoading(true);
    try {
      const result = await versionsApi.getVersionFileContent(skillName, viewingVersion.version, filePath);
      setFileContent(result.content);
    } catch (err) {
      setFileContent(`Error loading file: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setFileLoading(false);
    }
  };

  const handleCompare = async () => {
    if (!compareFrom || !compareTo) return;
    setDiffLoading(true);
    setDiffModalOpen(true);
    setDiffFiles([]);
    setDiffData(null);
    try {
      // Fetch file lists and version metadata in parallel
      const [fromFiles, toFiles, fromVer, toVer] = await Promise.all([
        versionsApi.getVersionFiles(skillName, compareFrom).catch(() => ({ files: [] })),
        versionsApi.getVersionFiles(skillName, compareTo).catch(() => ({ files: [] })),
        versionsApi.get(skillName, compareFrom).catch(() => null),
        versionsApi.get(skillName, compareTo).catch(() => null),
      ]);

      // Build hash maps for quick comparison
      const fromHashMap = new Map<string, string>();
      const toHashMap = new Map<string, string>();
      fromFiles.files?.forEach((f: VersionFile) => {
        if (f.content_hash) fromHashMap.set(f.file_path, f.content_hash);
      });
      toFiles.files?.forEach((f: VersionFile) => {
        if (f.content_hash) toHashMap.set(f.file_path, f.content_hash);
      });

      // Collect all file paths, then filter to only those with actual changes
      const changedFiles: VersionFile[] = [];

      // Check SKILL.md: compare skill_md content from version objects
      const fromMd = fromVer?.skill_md ?? "";
      const toMd = toVer?.skill_md ?? "";
      if (fromMd !== toMd) {
        changedFiles.push({ file_path: "SKILL.md", file_type: "skill" });
      }

      // Check other files: compare by content_hash
      const allFilePaths = new Set<string>();
      fromFiles.files?.forEach((f: VersionFile) => allFilePaths.add(f.file_path));
      toFiles.files?.forEach((f: VersionFile) => allFilePaths.add(f.file_path));

      Array.from(allFilePaths).forEach((path) => {
        const fromHash = fromHashMap.get(path);
        const toHash = toHashMap.get(path);
        // Include if file was added, removed, or content changed
        if (fromHash !== toHash) {
          changedFiles.push({
            file_path: path,
            file_type: path.startsWith("scripts/") ? "script" : "other",
          });
        }
      });

      // If no changes at all, still show SKILL.md so the modal isn't empty
      if (changedFiles.length === 0) {
        changedFiles.push({ file_path: "SKILL.md", file_type: "skill" });
      }

      setDiffFiles(changedFiles);

      // Default to first changed file
      const firstFile = changedFiles[0]?.file_path || "SKILL.md";
      setDiffFilePath(firstFile);

      const result = await versionsApi.diff(skillName, compareFrom, compareTo, firstFile);
      setDiffData({
        oldContent: result.old_content,
        newContent: result.new_content,
        diff: result.diff,
      });
    } catch (err) {
      setDiffData({
        oldContent: "",
        newContent: "",
        diff: `Error: ${err instanceof Error ? err.message : "Failed to compute diff"}`,
      });
    } finally {
      setDiffLoading(false);
    }
  };

  const handleDiffFileChange = async (filePath: string) => {
    if (!compareFrom || !compareTo) return;
    setDiffFilePath(filePath);
    setDiffLoading(true);
    try {
      const result = await versionsApi.diff(skillName, compareFrom, compareTo, filePath);
      setDiffData({
        oldContent: result.old_content,
        newContent: result.new_content,
        diff: result.diff,
      });
    } catch (err) {
      setDiffData({
        oldContent: "",
        newContent: "",
        diff: `Error: ${err instanceof Error ? err.message : "Failed to compute diff"}`,
      });
    } finally {
      setDiffLoading(false);
    }
  };

  const toggleCompareSelection = (version: string) => {
    if (compareFrom === version) {
      setCompareFrom(null);
    } else if (compareTo === version) {
      setCompareTo(null);
    } else if (!compareFrom) {
      setCompareFrom(version);
    } else if (!compareTo) {
      setCompareTo(version);
    } else {
      setCompareFrom(compareTo);
      setCompareTo(version);
    }
  };

  const handleSwitchVersion = async () => {
    if (!switchTarget) return;
    setSwitching(true);
    try {
      await versionsApi.rollback(skillName, switchTarget);
      toast.success(t("versions.switchSuccess", { version: switchTarget }));
      setSwitchConfirmOpen(false);
      setSwitchTarget(null);
      onVersionSwitch?.();
    } catch (err) {
      toast.error(
        t("versions.switchError", { error: err instanceof Error ? err.message : "Unknown error" })
      );
    } finally {
      setSwitching(false);
    }
  };

  const handleDeleteVersion = async () => {
    if (!deleteTarget) return;
    try {
      await deleteVersionMutation.mutateAsync(deleteTarget);
      toast.success(t("versions.deleteSuccess"));
      setDeleteConfirmOpen(false);
      setDeleteTarget(null);
      onVersionSwitch?.();
    } catch (err) {
      toast.error(
        `${t("versions.deleteError")}: ${err instanceof Error ? err.message : "Unknown error"}`
      );
    }
  };

  if (isLoading) {
    return <p className="text-muted-foreground">{t("versions.loading")}</p>;
  }

  if (versions.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-muted-foreground">{t("versions.empty")}</p>
        <Button
          className="mt-4"
          onClick={() => router.push(`/skills/${skillName}/versions/new`)}
        >
          {t("versions.createFirstVersion")}
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Compare toolbar */}
      {versions.length > 1 && (
        <div className="flex items-center gap-4 p-3 bg-muted rounded-md">
          <GitCompare className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">{t("versions.compare")}</span>
          <div className="flex items-center gap-2">
            <Badge variant={compareFrom ? "default" : "outline"} className="font-mono">
              {compareFrom || t("versions.select")}
            </Badge>
            <span className="text-muted-foreground">→</span>
            <Badge variant={compareTo ? "default" : "outline"} className="font-mono">
              {compareTo || t("versions.select")}
            </Badge>
          </div>
          <Button
            size="sm"
            variant="default"
            disabled={!compareFrom || !compareTo}
            onClick={handleCompare}
          >
            {t("versions.showDiff")}
          </Button>
          {(compareFrom || compareTo) && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => { setCompareFrom(null); setCompareTo(null); }}
            >
              {t("versions.clear")}
            </Button>
          )}
        </div>
      )}

      {/* Version Timeline */}
      <div className="relative">
        <div className="absolute left-[19px] top-0 bottom-0 w-0.5 bg-border" />

        <div className="space-y-0">
          {versions.map((version, index) => {
            const isSelected = compareFrom === version.version || compareTo === version.version;
            const isCurrent = version.version === currentVersion;
            const isFirst = index === 0;

            return (
              <div key={version.id} className="relative flex items-start gap-4 py-4">
                <div className="relative z-10 flex-shrink-0">
                  <button
                    onClick={() => toggleCompareSelection(version.version)}
                    className={`w-10 h-10 rounded-full border-2 flex items-center justify-center transition-all ${
                      isSelected
                        ? 'bg-primary border-primary text-primary-foreground'
                        : isCurrent
                          ? 'bg-green-500 border-green-500 text-white'
                          : 'bg-background border-border hover:border-primary'
                    }`}
                    title={isSelected ? t("versions.clickToDeselect") : t("versions.clickToSelect")}
                  >
                    {isSelected ? (
                      <span className="text-xs font-bold">
                        {compareFrom === version.version ? '1' : '2'}
                      </span>
                    ) : (
                      <Clock className="h-4 w-4 text-muted-foreground" />
                    )}
                  </button>
                </div>

                <div
                  className={`flex-1 p-4 rounded-lg border transition-colors cursor-pointer hover:bg-muted/50 ${
                    isSelected ? 'border-primary bg-primary/5' : ''
                  }`}
                  onClick={() => handleViewVersion(version)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono font-semibold text-lg">{version.version}</span>
                        {isCurrent && (
                          <Badge variant="outline-success">
                            {t("versions.current")}
                          </Badge>
                        )}
                        {isFirst && !isCurrent && (
                          <Badge variant="outline" className="text-xs">
                            {t("versions.latest")}
                          </Badge>
                        )}
                      </div>
                      {version.commit_message && (
                        <p className="text-sm text-muted-foreground mt-1">
                          {version.commit_message}
                        </p>
                      )}
                      <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatDateTime(version.created_at)}
                        </span>
                        {version.created_by && (
                          <span className="flex items-center gap-1">
                            <User className="h-3 w-3" />
                            {version.created_by}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {!isCurrent && (
                        <Button
                          size="sm"
                          variant="default"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSwitchTarget(version.version);
                            setSwitchConfirmOpen(true);
                          }}
                        >
                          <ArrowRightLeft className="h-3 w-3 mr-1" />
                          {t("versions.switchTo")}
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleViewVersion(version);
                        }}
                      >
                        {t("versions.view")}
                      </Button>
                      {!isCurrent && versions.length > 1 && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-destructive hover:bg-destructive hover:text-destructive-foreground"
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeleteTarget(version.version);
                            setDeleteConfirmOpen(true);
                          }}
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* View Version Modal */}
      <Dialog open={viewModalOpen} onOpenChange={setViewModalOpen}>
        <DialogContent className="max-w-5xl max-h-[85vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>
              {t("versions.viewVersion", { version: viewingVersion?.version })}
              {viewingVersion?.version === currentVersion && ` ${t("versions.viewVersionCurrent")}`}
            </DialogTitle>
            <DialogDescription>
              {viewingVersion?.commit_message || t("versions.noCommitMessage")}
              {viewingVersion?.created_at && ` • ${formatDateTime(viewingVersion.created_at)}`}
            </DialogDescription>
          </DialogHeader>
          <div className="flex-1 overflow-hidden flex gap-4">
            <div className="w-48 flex-shrink-0 border-r pr-4 overflow-auto">
              <h4 className="text-sm font-medium mb-2">{t("versions.files")}</h4>
              <div className="space-y-1">
                <button
                  className={`w-full text-left px-2 py-1 rounded text-sm font-mono ${
                    selectedFile === "SKILL.md" ? "bg-primary text-primary-foreground" : "hover:bg-muted"
                  }`}
                  onClick={() => handleSelectFile("SKILL.md")}
                >
                  SKILL.md
                </button>
                {versionFiles.map((file) => (
                  <button
                    key={file.file_path}
                    className={`w-full text-left px-2 py-1 rounded text-sm font-mono truncate ${
                      selectedFile === file.file_path ? "bg-primary text-primary-foreground" : "hover:bg-muted"
                    }`}
                    onClick={() => handleSelectFile(file.file_path)}
                    title={file.file_path}
                  >
                    {file.file_path}
                  </button>
                ))}
                {versionFiles.length === 0 && (
                  <p className="text-xs text-muted-foreground italic">{t("versions.noAdditionalFiles")}</p>
                )}
              </div>
            </div>
            <div className="flex-1 overflow-auto">
              {viewLoading || fileLoading ? (
                <p className="text-muted-foreground">{t("versions.loading")}</p>
              ) : fileContent ? (
                <SyntaxHighlighter
                  language={getLanguageFromFilename(selectedFile || '')}
                  style={oneDark}
                  customStyle={{
                    margin: 0,
                    borderRadius: '0.375rem',
                    fontSize: '0.875rem',
                  }}
                  showLineNumbers
                >
                  {fileContent}
                </SyntaxHighlighter>
              ) : (
                <p className="text-muted-foreground">{t("versions.noContent")}</p>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setViewModalOpen(false)}>
              {t("versions.close")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Switch Version Confirm Dialog */}
      <Dialog open={switchConfirmOpen} onOpenChange={(open) => {
        if (!switching) setSwitchConfirmOpen(open);
      }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{t("versions.switchVersion")}</DialogTitle>
            <DialogDescription>
              {t("versions.switchConfirm", { version: switchTarget })}
              {' '}{t("versions.switchDescription")}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setSwitchConfirmOpen(false)}
              disabled={switching}
            >
              {t("versions.cancel")}
            </Button>
            <Button onClick={handleSwitchVersion} disabled={switching}>
              {switching ? (
                <>
                  <Spinner size="sm" className="mr-2" />
                  {t("versions.switching")}
                </>
              ) : (
                t("versions.confirm")
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Version Confirm Dialog */}
      <Dialog open={deleteConfirmOpen} onOpenChange={(open) => {
        if (!deleteVersionMutation.isPending) setDeleteConfirmOpen(open);
      }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{t("versions.deleteConfirm", { version: deleteTarget })}</DialogTitle>
            <DialogDescription>
              {t("versions.deleteDescription")}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteConfirmOpen(false)}
              disabled={deleteVersionMutation.isPending}
            >
              {t("versions.cancel")}
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteVersion}
              disabled={deleteVersionMutation.isPending}
            >
              {deleteVersionMutation.isPending ? (
                <>
                  <Spinner size="sm" className="mr-2" />
                  {t("versions.deleting")}
                </>
              ) : (
                t("delete.deleteButton")
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Diff Modal */}
      <Dialog open={diffModalOpen} onOpenChange={(open) => {
        setDiffModalOpen(open);
        if (!open) setIsFullscreen(false);
      }}>
        <DialogContent className={`overflow-hidden flex flex-col ${
          isFullscreen
            ? 'max-w-[100vw] max-h-[100vh] w-[100vw] h-[100vh] rounded-none'
            : 'max-w-6xl max-h-[85vh]'
        }`}>
          <DialogHeader>
            <div className="flex items-center justify-between">
              <div>
                <DialogTitle className="flex items-center gap-2">
                  <GitCompare className="h-5 w-5" />
                  {t("versions.versionDiff")}
                </DialogTitle>
                <DialogDescription>
                  {t("versions.comparingVersions", { from: compareFrom, to: compareTo })}
                </DialogDescription>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsFullscreen(!isFullscreen)}
              >
                {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
              </Button>
            </div>
          </DialogHeader>

          <div className="flex items-center justify-between gap-4 pb-3 border-b">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">{t("versions.file")}</span>
                {diffFiles.length > 1 ? (
                  <select
                    value={diffFilePath}
                    onChange={(e) => handleDiffFileChange(e.target.value)}
                    className="text-sm border rounded px-2 py-1 font-mono bg-background"
                    disabled={diffLoading}
                  >
                    {diffFiles.map((file) => (
                      <option key={file.file_path} value={file.file_path}>
                        {file.file_path}
                      </option>
                    ))}
                  </select>
                ) : (
                  <span className="text-sm font-mono font-medium">{diffFilePath}</span>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">{t("versions.viewMode")}</span>
              <div className="flex rounded-md border overflow-hidden">
                <button
                  onClick={() => setSplitView(true)}
                  className={`px-3 py-1 text-sm ${splitView ? 'bg-primary text-primary-foreground' : 'bg-background hover:bg-muted'}`}
                >
                  {t("versions.split")}
                </button>
                <button
                  onClick={() => setSplitView(false)}
                  className={`px-3 py-1 text-sm ${!splitView ? 'bg-primary text-primary-foreground' : 'bg-background hover:bg-muted'}`}
                >
                  {t("versions.unified")}
                </button>
              </div>
            </div>
          </div>

          <div className="flex-1 overflow-auto min-w-0">
            {diffLoading ? (
              <div className="flex items-center justify-center py-12">
                <Spinner size="lg" className="mr-3" />
                <span className="text-muted-foreground">{t("versions.computingDiff")}</span>
              </div>
            ) : diffData ? (
              diffData.oldContent === diffData.newContent ? (
                <div className="flex items-center justify-center py-12 text-muted-foreground">
                  {t("versions.noDifferences")}
                </div>
              ) : (
                <DiffViewer
                  oldValue={diffData.oldContent}
                  newValue={diffData.newContent}
                  oldTitle={`v${compareFrom}`}
                  newTitle={`v${compareTo}`}
                  splitView={splitView}
                  showDiffOnly={true}
                />
              )
            ) : (
              <div className="flex items-center justify-center py-12 text-muted-foreground">
                {t("versions.selectVersionsToCompare")}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDiffModalOpen(false)}>
              {t("versions.close")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

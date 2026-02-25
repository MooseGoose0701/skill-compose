"use client";

import React from "react";
import type { SkillResources } from "@/lib/api";
import type { SkillVersion } from "@/types/skill";
import { versionsApi } from "@/lib/api";
import { ResourceItem } from "./resource-item";
import { ChevronRight, ChevronDown, Folder, FolderOpen, FilePlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useTranslation } from "@/i18n/client";

interface ResourcesListProps {
  skillName: string;
  resources: SkillResources | null;
  isLoading: boolean;
  currentVersion?: SkillVersion | null;
  onVersionCreated?: () => void;
}

interface FileNode {
  name: string;
  path: string;  // Full path for files
  isFile: boolean;
  children: Map<string, FileNode>;
}

// Build a tree structure from flat file paths
function buildFileTree(files: string[]): FileNode {
  const root: FileNode = { name: "", path: "", isFile: false, children: new Map() };

  for (const filePath of files) {
    const parts = filePath.split("/");
    let current = root;

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const isLastPart = i === parts.length - 1;

      if (!current.children.has(part)) {
        current.children.set(part, {
          name: part,
          path: isLastPart ? filePath : parts.slice(0, i + 1).join("/"),
          isFile: isLastPart,
          children: new Map(),
        });
      }
      current = current.children.get(part)!;
    }
  }

  return root;
}

// Sort children: folders first, then files, both alphabetically
function getSortedChildren(node: FileNode): FileNode[] {
  const children = Array.from(node.children.values());
  return children.sort((a, b) => {
    if (a.isFile !== b.isFile) {
      return a.isFile ? 1 : -1; // Folders first
    }
    return a.name.localeCompare(b.name);
  });
}

interface FolderNodeProps {
  node: FileNode;
  skillName: string;
  currentVersion?: string;
  onVersionCreated?: () => void;
  depth?: number;
}

function FolderNode({ node, skillName, currentVersion, onVersionCreated, depth = 0 }: FolderNodeProps) {
  const [isExpanded, setIsExpanded] = React.useState(depth < 1); // Auto-expand first level
  const sortedChildren = getSortedChildren(node);

  if (sortedChildren.length === 0) return null;

  return (
    <div className="space-y-1">
      {/* Folder header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-1 text-sm font-medium hover:bg-muted/50 rounded px-1 py-0.5 w-full text-left"
        style={{ paddingLeft: `${depth * 16}px` }}
      >
        {isExpanded ? (
          <>
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
            <FolderOpen className="h-4 w-4 text-yellow-500" />
          </>
        ) : (
          <>
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
            <Folder className="h-4 w-4 text-yellow-500" />
          </>
        )}
        <span className="ml-1">{node.name}/</span>
        <span className="text-xs text-muted-foreground ml-1">({sortedChildren.length})</span>
      </button>

      {/* Children */}
      {isExpanded && (
        <div className="space-y-1">
          {sortedChildren.map((child) => (
            child.isFile ? (
              <div key={child.path} style={{ paddingLeft: `${(depth + 1) * 16 + 8}px` }}>
                <ResourceItem
                  skillName={skillName}
                  resourceType="other"
                  filename={child.path}
                  currentVersion={currentVersion}
                  onVersionCreated={onVersionCreated}
                />
              </div>
            ) : (
              <FolderNode
                key={child.path}
                node={child}
                skillName={skillName}
                currentVersion={currentVersion}
                onVersionCreated={onVersionCreated}
                depth={depth + 1}
              />
            )
          ))}
        </div>
      )}
    </div>
  );
}

interface CreateFileDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  skillName: string;
  existingFiles: string[];
  onVersionCreated?: () => void;
}

function CreateFileDialog({
  open,
  onOpenChange,
  skillName,
  existingFiles,
  onVersionCreated,
}: CreateFileDialogProps) {
  const { t } = useTranslation('skills');
  const [filePath, setFilePath] = React.useState("");
  const [content, setContent] = React.useState("");
  const [commitMessage, setCommitMessage] = React.useState("");
  const [isSaving, setIsSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const handleClose = () => {
    setFilePath("");
    setContent("");
    setCommitMessage("");
    setError(null);
    onOpenChange(false);
  };

  const handleSave = async () => {
    if (!filePath.trim()) {
      setError(t('files.createFilePathRequired'));
      return;
    }

    const normalized = filePath.trim().replace(/^\/+/, '');
    if (!normalized) {
      setError(t('files.createFilePathRequired'));
      return;
    }

    if (normalized.toUpperCase() === 'SKILL.MD') {
      setError(t('files.skillMdReserved'));
      return;
    }

    if (existingFiles.includes(normalized)) {
      setError(t('files.createFileExists'));
      return;
    }

    const BLOCKED_EXTENSIONS = ['.pyc', '.pyo', '.pyd', '.class', '.o', '.a', '.so', '.dylib', '.dll', '.exe', '.wasm'];
    const ext = normalized.includes('.') ? ('.' + normalized.split('.').pop()!.toLowerCase()) : '';
    if (ext && BLOCKED_EXTENSIONS.includes(ext)) {
      setError(t('files.blockedFileType', { ext }));
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      await versionsApi.create(skillName, {
        commit_message: commitMessage || t('files.createdFile', { filename: normalized }),
        files_content: { [normalized]: content },
      });
      handleClose();
      onVersionCreated?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : t('files.failedToCreateFile'));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>{t('files.createFile')}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div>
            <label className="text-sm font-medium mb-1 block">{t('files.filePath')}</label>
            <Input
              placeholder={t('files.filePathPlaceholder')}
              value={filePath}
              onChange={(e) => { setFilePath(e.target.value); setError(null); }}
              className="font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground mt-1">{t('files.filePathHelp')}</p>
          </div>
          <div>
            <label className="text-sm font-medium mb-1 block">{t('files.fileContent')}</label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="w-full h-64 font-mono text-xs p-3 border rounded-md resize-none bg-background"
              placeholder={t('files.fileContentPlaceholder')}
              spellCheck={false}
            />
          </div>
          <div>
            <label className="text-sm font-medium mb-1 block">{t('files.commitMessage')}</label>
            <Input
              placeholder={t('files.commitMessagePlaceholder')}
              value={commitMessage}
              onChange={(e) => setCommitMessage(e.target.value)}
            />
          </div>
          {error && <p className="text-red-500 text-sm">{error}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={isSaving}>
            {t('files.cancel')}
          </Button>
          <Button onClick={handleSave} disabled={isSaving || !filePath.trim()}>
            {isSaving ? t('files.creating') : t('files.createFileButton')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ResourcesList({
  skillName,
  resources,
  isLoading,
  currentVersion,
  onVersionCreated,
}: ResourcesListProps) {
  const { t } = useTranslation('skills');
  const [showCreateDialog, setShowCreateDialog] = React.useState(false);

  if (isLoading) {
    return <p className="text-muted-foreground">{t('files.loadingResources')}</p>;
  }

  // Combine all files into a single list with full paths
  const allFiles: string[] = [];
  if (resources) {
    // Add standard directories with their prefixes
    resources.scripts.forEach(f => allFiles.push(`scripts/${f}`));
    resources.references.forEach(f => allFiles.push(`references/${f}`));
    resources.assets.forEach(f => allFiles.push(`assets/${f}`));
    // Other files already have full paths
    if (resources.other) {
      allFiles.push(...resources.other);
    }
  }

  const hasResources = allFiles.length > 0;
  const fileTree = buildFileTree(allFiles);

  return (
    <div className="space-y-6">
      {/* SKILL.md - Always show, expanded by default */}
      <div>
        <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
          <span className="text-orange-500">📄</span> {t('files.skillDefinition')}
        </h4>
        <div className="space-y-2">
          <ResourceItem
            skillName={skillName}
            resourceType="skill"
            filename="SKILL.md"
            initialContent={currentVersion?.skill_md || ""}
            currentVersion={currentVersion?.version}
            onVersionCreated={onVersionCreated}
            defaultExpanded={true}
          />
        </div>
      </div>

      {/* Files - displayed as folder tree */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-sm font-medium flex items-center gap-2">
            <span className="text-blue-500">📁</span> {t('files.title')}
          </h4>
          {currentVersion && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => setShowCreateDialog(true)}
              className="h-7 text-xs"
            >
              <FilePlus className="h-3.5 w-3.5 mr-1" />
              {t('files.createFile')}
            </Button>
          )}
        </div>
        {hasResources ? (
          <div className="space-y-1 border rounded-md p-3 bg-muted/30">
            {getSortedChildren(fileTree).map((child) => (
              child.isFile ? (
                <div key={child.path} className="pl-2">
                  <ResourceItem
                    skillName={skillName}
                    resourceType="other"
                    filename={child.path}
                    currentVersion={currentVersion?.version}
                    onVersionCreated={onVersionCreated}
                  />
                </div>
              ) : (
                <FolderNode
                  key={child.path}
                  node={child}
                  skillName={skillName}
                  currentVersion={currentVersion?.version}
                  onVersionCreated={onVersionCreated}
                />
              )
            ))}
          </div>
        ) : (
          <p className="text-muted-foreground text-sm">
            {currentVersion ? t('files.empty') : t('files.noResources')}
          </p>
        )}
      </div>

      {/* Create File Dialog */}
      <CreateFileDialog
        open={showCreateDialog}
        onOpenChange={setShowCreateDialog}
        skillName={skillName}
        existingFiles={allFiles}
        onVersionCreated={onVersionCreated}
      />
    </div>
  );
}

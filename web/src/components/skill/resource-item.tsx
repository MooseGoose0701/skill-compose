"use client";

import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { resourcesApi, versionsApi } from "@/lib/api";
import { getLanguageFromFilename } from "@/lib/formatters";
import { useTranslation } from "@/i18n/client";

interface ResourceItemProps {
  skillName: string;
  resourceType: string;
  filename: string;
  initialContent?: string;
  currentVersion?: string;
  onVersionCreated?: () => void;
  defaultExpanded?: boolean;
}

export function ResourceItem({
  skillName,
  resourceType,
  filename,
  initialContent,
  currentVersion,
  onVersionCreated,
  defaultExpanded = false,
}: ResourceItemProps) {
  const { t } = useTranslation('skills');
  const [isOpen, setIsOpen] = React.useState(defaultExpanded);
  const [content, setContent] = React.useState<string | null>(initialContent ?? null);
  const [originalContent, setOriginalContent] = React.useState<string | null>(initialContent ?? null);
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [isEditing, setIsEditing] = React.useState(false);
  const [isSaving, setIsSaving] = React.useState(false);
  const [commitMessage, setCommitMessage] = React.useState("");

  // Sync content from parent when initialContent changes (e.g. after version refetch)
  // but only when not editing, to avoid overwriting user's in-progress edits.
  React.useEffect(() => {
    if (!isEditing && initialContent != null && initialContent !== "") {
      setContent(initialContent);
      setOriginalContent(initialContent);
    }
  }, [initialContent, isEditing]);

  const language = React.useMemo(() => getLanguageFromFilename(filename), [filename]);

  const isEditable = React.useMemo(() => {
    const textExtensions = [
      '.md', '.txt', '.py', '.js', '.ts', '.tsx', '.jsx', '.json', '.yaml', '.yml',
      '.sh', '.bash', '.css', '.scss', '.less', '.html', '.xml', '.csv', '.toml', '.ini',
      '.cfg', '.conf', '.env', '.gitignore', '.dockerfile', '.vue', '.svelte'
    ];
    const lowerName = filename.toLowerCase();
    return textExtensions.some(ext => lowerName.endsWith(ext)) ||
           lowerName === 'skill.md' ||
           !lowerName.includes('.');
  }, [filename]);

  const handleToggle = async () => {
    if (isEditing) return;

    if (isOpen) {
      setIsOpen(false);
      return;
    }

    if (content !== null) {
      setIsOpen(true);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      if (resourceType === "skill") {
        setContent(initialContent || "");
        setOriginalContent(initialContent || "");
      } else {
        let fileContent: string;
        // For "other" files, the filename is already the full path (e.g., rules/animations.md)
        // For standard types (scripts, references, assets), we need to construct the path
        const isOtherType = resourceType === "other";
        const filePath = isOtherType ? filename : `${resourceType}/${filename}`;

        try {
          if (isOtherType) {
            // "other" files: go directly to database version files
            if (!currentVersion) throw new Error("No version available");
            const result = await versionsApi.getVersionFileContent(skillName, currentVersion, filePath);
            fileContent = result.content;
          } else {
            // Standard types: try filesystem first
            fileContent = await resourcesApi.getFileContent(skillName, resourceType, filename);
          }
        } catch (fsErr: unknown) {
          // Filesystem 404 → try database version files
          const err = fsErr as Record<string, unknown> | null;
          if (err && typeof err === 'object' && 'status' in err && err.status === 404 && currentVersion) {
            const result = await versionsApi.getVersionFileContent(skillName, currentVersion, filePath);
            fileContent = result.content;
          } else {
            throw fsErr;
          }
        }
        setContent(fileContent);
        setOriginalContent(fileContent);
      }
      setIsOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('files.failedToLoadFile'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsEditing(true);
    setIsOpen(true);
  };

  const handleCancel = (e: React.MouseEvent) => {
    e.stopPropagation();
    setContent(originalContent);
    setIsEditing(false);
    setCommitMessage("");
    setError(null);
  };

  const handleSave = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!currentVersion || content === null) return;

    setIsSaving(true);
    setError(null);

    try {
      const request: {
        version?: string;
        skill_md?: string;
        files_content?: Record<string, string>;
        commit_message?: string;
      } = {
        commit_message: commitMessage || t('files.updatedFile', { filename }),
      };

      if (resourceType === "skill") {
        request.skill_md = content;
      } else {
        // For "other" files, filename is already the full path
        const filePath = resourceType === "other" ? filename : `${resourceType}/${filename}`;
        request.files_content = {
          [filePath]: content
        };
      }

      await versionsApi.create(skillName, request);

      setIsEditing(false);
      setOriginalContent(content);
      setCommitMessage("");
      onVersionCreated?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : t('files.failedToSave'));
    } finally {
      setIsSaving(false);
    }
  };

  const hasChanges = content !== originalContent;

  return (
    <Card className={`transition-colors ${!isEditing ? 'cursor-pointer hover:bg-muted/50' : ''}`}>
      <CardContent className="p-3" onClick={!isEditing ? handleToggle : undefined}>
        <div className="flex items-center justify-between">
          <code className="text-sm font-mono">{filename}</code>
          <div className="flex items-center gap-2">
            {isEditing ? (
              <>
                <Button size="sm" variant="ghost" onClick={handleCancel} disabled={isSaving}>
                  {t('files.cancel')}
                </Button>
                <Button size="sm" onClick={handleSave} disabled={isSaving || !hasChanges}>
                  {isSaving ? t('files.saving') : t('files.save')}
                </Button>
              </>
            ) : (
              <>
                {isOpen && isEditable && currentVersion && (
                  <Button size="sm" variant="ghost" onClick={handleEdit}>
                    {t('files.edit')}
                  </Button>
                )}
                <span className="text-muted-foreground text-xs">
                  {isLoading ? "..." : isOpen ? "▼" : "▶"}
                </span>
              </>
            )}
          </div>
        </div>

        {isEditing && (
          <div className="mt-3" onClick={(e) => e.stopPropagation()}>
            <input
              type="text"
              placeholder={t('files.commitMessagePlaceholder')}
              value={commitMessage}
              onChange={(e) => setCommitMessage(e.target.value)}
              className="w-full px-3 py-2 text-sm border rounded-md bg-background"
            />
          </div>
        )}

        {error && (
          <p className="text-red-500 text-sm mt-2">{error}</p>
        )}

        {isOpen && content !== null && (
          <div className="mt-3" onClick={(e) => e.stopPropagation()}>
            {isEditing ? (
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                className="w-full h-80 font-mono text-xs p-3 border rounded-md resize-none bg-background"
                spellCheck={false}
              />
            ) : language ? (
              <div className="rounded-md max-h-96 overflow-auto">
                <SyntaxHighlighter
                  language={language}
                  style={oneDark}
                  customStyle={{
                    margin: 0,
                    padding: '12px',
                    fontSize: '12px',
                    borderRadius: '6px',
                    minWidth: 'fit-content',
                  }}
                >
                  {content || t('files.emptyFile')}
                </SyntaxHighlighter>
              </div>
            ) : (
              <pre className="p-3 bg-muted rounded-md text-xs font-mono overflow-auto max-h-96 whitespace-pre-wrap">
                {content || t('files.emptyFile')}
              </pre>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

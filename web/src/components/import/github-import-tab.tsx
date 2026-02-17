"use client";

import React from "react";
import { Github, Link, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { transferApi } from "@/lib/api";
import { useTranslation } from "@/i18n/client";
import type { ImportResult } from "./import-result-display";
import { ImportErrorDisplay, ImportSuccessDisplay } from "./import-result-display";
import type { ConflictInfo } from "./conflict-dialog";

interface GitHubImportTabProps {
  onConflict: (info: ConflictInfo) => void;
  onResolveConflict: (doImport: (action?: string) => Promise<void>) => void;
}

export function GitHubImportTab({ onConflict, onResolveConflict }: GitHubImportTabProps) {
  const { t } = useTranslation("import");
  const { t: tc } = useTranslation("common");

  const [githubUrl, setGithubUrl] = React.useState("");
  const [isImporting, setIsImporting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<ImportResult | null>(null);

  const isValidGitHubUrl = (url: string): boolean => {
    const pattern = /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+(\/tree\/[\w.-]+(\/.*)?)?$/;
    return pattern.test(url);
  };

  const getGitHubUrlHint = (url: string): string | null => {
    if (!url || isValidGitHubUrl(url)) return null;
    if (!url.startsWith("http")) return t("github.hints.httpsRequired");
    if (!url.includes("github.com")) return t("github.hints.githubRequired");
    if (url.startsWith("http://github.com")) return t("github.hints.useHttps");
    const parts = url.replace("https://github.com/", "").split("/");
    if (parts.length < 2 || !parts[1]) return t("github.hints.ownerRepoRequired");
    if (parts.length > 2 && parts[2] !== "tree") return t("github.hints.treeFormat");
    if (parts[2] === "tree" && (!parts[3] || !parts[3].trim())) return t("github.hints.branchRequired");
    return t("github.hints.expectedFormat");
  };

  const doImport = async (conflictAction?: string) => {
    setIsImporting(true);
    setError(null);
    try {
      const importResult = await transferApi.importFromGitHub({
        url: githubUrl.trim(),
        conflictAction,
      });
      setResult(importResult);
      setGithubUrl("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("status.githubError"));
    } finally {
      setIsImporting(false);
    }
  };

  const handleImport = async () => {
    if (!githubUrl.trim()) return;
    setIsImporting(true);
    setError(null);
    setResult(null);

    try {
      const checkResult = await transferApi.importFromGitHub({
        url: githubUrl.trim(),
        checkOnly: true,
      });

      if (checkResult.conflict) {
        onConflict({
          skillName: checkResult.existing_skill || checkResult.skill_name,
          existingVersion: checkResult.existing_version || "unknown",
          source: "github",
        });
        onResolveConflict(doImport);
        setIsImporting(false);
        return;
      }

      await doImport();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("status.githubError"));
      setIsImporting(false);
    }
  };

  const handleReset = () => {
    setGithubUrl("");
    setError(null);
    setResult(null);
  };

  const hint = githubUrl ? getGitHubUrlHint(githubUrl) : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Github className="h-5 w-5" />
          {t("github.title")}
        </CardTitle>
        <CardDescription>{t("github.description")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="github-url">{t("github.urlLabel")}</Label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Link className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                id="github-url"
                placeholder={t("github.placeholder")}
                value={githubUrl}
                onChange={(e) => { setGithubUrl(e.target.value); setError(null); }}
                className="pl-10"
                disabled={isImporting}
              />
            </div>
          </div>
          <p className="text-xs text-muted-foreground">{t("github.examples")}</p>
        </div>

        {hint && (
          <div className="flex items-start gap-2 text-sm text-amber-600 dark:text-amber-400">
            <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
            <span>{hint}</span>
          </div>
        )}

        {error && <ImportErrorDisplay error={error} />}
        {result?.success && <ImportSuccessDisplay result={result} />}

        <div className="flex gap-3">
          {!result && (
            <>
              <Button
                onClick={handleImport}
                disabled={!githubUrl.trim() || !isValidGitHubUrl(githubUrl) || isImporting}
                className="flex-1"
              >
                {isImporting ? (
                  <>
                    <Spinner size="md" className="mr-2 text-white" />
                    {t("status.importing")}
                  </>
                ) : (
                  <>
                    <Github className="h-4 w-4 mr-2" />
                    {t("github.button")}
                  </>
                )}
              </Button>
              {githubUrl && (
                <Button variant="outline" onClick={handleReset} disabled={isImporting}>
                  {tc("actions.clear")}
                </Button>
              )}
            </>
          )}
          {result?.success && (
            <Button variant="outline" onClick={handleReset} className="flex-1">
              {t("status.importAnother")}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

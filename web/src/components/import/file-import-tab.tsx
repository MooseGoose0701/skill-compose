"use client";

import React from "react";
import { Upload, FileArchive } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { useTranslation } from "@/i18n/client";
import type { ImportResult } from "./import-result-display";
import { ImportErrorDisplay, ImportSuccessDisplay } from "./import-result-display";
import type { ConflictInfo } from "./conflict-dialog";

interface FileImportTabProps {
  onConflict: (info: ConflictInfo) => void;
  onResolveConflict: (doImport: (action?: string) => Promise<void>) => void;
}

export function FileImportTab({ onConflict, onResolveConflict }: FileImportTabProps) {
  const { t } = useTranslation("import");
  const { t: tc } = useTranslation("common");

  const [isDragging, setIsDragging] = React.useState(false);
  const [isUploading, setIsUploading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<ImportResult | null>(null);
  const [selectedFile, setSelectedFile] = React.useState<File | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const handleFileSelect = (file: File) => {
    setError(null);
    setResult(null);
    if (!file.name.endsWith(".skill") && !file.name.endsWith(".zip")) {
      setError(t("file.invalidFile"));
      return;
    }
    setSelectedFile(file);
  };

  const doImport = async (conflictAction?: string) => {
    if (!selectedFile) return;
    setIsUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:62610";
      const url = conflictAction
        ? `${apiUrl}/api/v1/registry/import?conflict_action=${conflictAction}`
        : `${apiUrl}/api/v1/registry/import`;

      const response = await fetch(url, { method: "POST", body: formData });
      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        const detail = errorData?.detail;
        if (typeof detail === "object" && detail.message) throw new Error(detail.message);
        throw new Error(detail || `Import failed: ${response.statusText}`);
      }

      const importResult: ImportResult = await response.json();
      setResult(importResult);
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err) {
      setError(err instanceof Error ? err.message : t("status.genericError"));
    } finally {
      setIsUploading(false);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    setIsUploading(true);
    setError(null);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:62610";

      const checkResponse = await fetch(`${apiUrl}/api/v1/registry/import?check_only=true`, {
        method: "POST",
        body: formData,
      });
      if (!checkResponse.ok) {
        const errorData = await checkResponse.json().catch(() => null);
        throw new Error(errorData?.detail || `Check failed: ${checkResponse.statusText}`);
      }

      const checkResult: ImportResult = await checkResponse.json();
      if (checkResult.conflict) {
        onConflict({
          skillName: checkResult.existing_skill || checkResult.skill_name,
          existingVersion: checkResult.existing_version || "unknown",
          source: "file",
        });
        onResolveConflict(doImport);
        setIsUploading(false);
        return;
      }

      await doImport();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("status.genericError"));
      setIsUploading(false);
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    setError(null);
    setResult(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("file.title")}</CardTitle>
        <CardDescription>{t("file.description")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div
          className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
            isDragging ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"
          } ${isUploading ? "opacity-50 pointer-events-none" : "cursor-pointer"}`}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={(e) => { e.preventDefault(); setIsDragging(false); }}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);
            const files = e.dataTransfer.files;
            if (files.length > 0) handleFileSelect(files[0]);
          }}
          onClick={() => !isUploading && fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".skill,.zip"
            onChange={(e) => { if (e.target.files?.[0]) handleFileSelect(e.target.files[0]); }}
            className="hidden"
            disabled={isUploading}
          />
          {selectedFile ? (
            <div className="space-y-3">
              <FileArchive className="h-12 w-12 mx-auto text-primary" />
              <div>
                <p className="font-medium">{selectedFile.name}</p>
                <p className="text-sm text-muted-foreground">
                  {(selectedFile.size / 1024).toFixed(1)} KB
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <Upload className="h-12 w-12 mx-auto text-muted-foreground" />
              <div>
                <p className="font-medium">{t("file.dropHere")}</p>
                <p className="text-sm text-muted-foreground">{t("file.orClickToBrowse")}</p>
              </div>
            </div>
          )}
        </div>

        {error && <ImportErrorDisplay error={error} />}
        {result?.success && <ImportSuccessDisplay result={result} />}

        <div className="flex gap-3">
          {selectedFile && !result && (
            <>
              <Button onClick={handleUpload} disabled={isUploading} className="flex-1">
                {isUploading ? (
                  <>
                    <Spinner size="md" className="mr-2 text-white" />
                    {t("status.importing")}
                  </>
                ) : (
                  <>
                    <Upload className="h-4 w-4 mr-2" />
                    {t("file.button")}
                  </>
                )}
              </Button>
              <Button variant="outline" onClick={handleReset} disabled={isUploading}>
                {tc("actions.cancel")}
              </Button>
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

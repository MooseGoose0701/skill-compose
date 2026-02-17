"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { skillsApi, versionsApi } from "@/lib/api";
import type { CreateVersionRequest } from "@/types/skill";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CodeEditor } from "@/components/editor/code-editor";
import { useTranslation } from "@/i18n/client";

const DEFAULT_SKILL_MD = `---
name: skill-name
description: Short description of the skill
---

# Skill Name

## Description

Describe what this skill does and when it should be used.

## Usage

Explain how to use this skill.

## Examples

Provide examples of input/output.
`;

const DEFAULT_SCHEMA = JSON.stringify(
  {
    input: {
      type: "object",
      properties: {},
    },
    output: {
      type: "object",
      properties: {},
    },
  },
  null,
  2
);

const DEFAULT_MANIFEST = JSON.stringify(
  {
    name: "skill-name",
    version: "1.0.0",
    description: "Short description",
    tags: [],
    triggers: [],
    dependencies: {
      mcp: [],
      tools: [],
      skills: [],
    },
  },
  null,
  2
);

export default function NewVersionPage() {
  const { t } = useTranslation("skills");
  const { t: tc } = useTranslation("common");
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const skillName = params.name as string;

  // Fetch skill info
  const { data: skill, isLoading: skillLoading } = useQuery({
    queryKey: ["skill", skillName],
    queryFn: () => skillsApi.get(skillName),
  });

  // Form state
  const [version, setVersion] = useState("");
  const [commitMessage, setCommitMessage] = useState("");
  const [skillMd, setSkillMd] = useState(
    DEFAULT_SKILL_MD.replace("skill-name", skillName)
  );
  const [schemaJson, setSchemaJson] = useState(DEFAULT_SCHEMA);
  const [manifestJson, setManifestJson] = useState(
    DEFAULT_MANIFEST.replace("skill-name", skillName)
  );
  const [errors, setErrors] = useState<Record<string, string>>({});

  const createMutation = useMutation({
    mutationFn: (data: {
      version: string;
      skill_md?: string;
      schema_json?: Record<string, unknown>;
      manifest_json?: Record<string, unknown>;
      commit_message?: string;
    }) => versionsApi.create(skillName, data as CreateVersionRequest),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["skill", skillName] });
      queryClient.invalidateQueries({ queryKey: ["versions", skillName] });
      router.push(`/skills/${skillName}`);
    },
    onError: (error: Error) => {
      setErrors({ submit: error.message });
    },
  });

  const validateVersion = (value: string): string | null => {
    if (!value) return t("newVersion.validation.versionRequired");
    if (!/^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$/.test(value)) {
      return t("newVersion.validation.versionInvalid");
    }
    return null;
  };

  const validateJson = (value: string, name: string): string | null => {
    if (!value.trim()) return null;
    try {
      JSON.parse(value);
      return null;
    } catch {
      return t("newVersion.validation.invalidJson", { name });
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const newErrors: Record<string, string> = {};

    const versionError = validateVersion(version);
    if (versionError) newErrors.version = versionError;

    const schemaError = validateJson(schemaJson, "schema");
    if (schemaError) newErrors.schema = schemaError;

    const manifestError = validateJson(manifestJson, "manifest");
    if (manifestError) newErrors.manifest = manifestError;

    if (!skillMd.trim()) {
      newErrors.skillMd = t("newVersion.validation.skillMdRequired");
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setErrors({});
    createMutation.mutate({
      version,
      skill_md: skillMd,
      schema_json: schemaJson.trim() ? JSON.parse(schemaJson) : undefined,
      manifest_json: manifestJson.trim() ? JSON.parse(manifestJson) : undefined,
      commit_message: commitMessage || undefined,
    });
  };

  if (skillLoading) {
    return (
      <div className="container mx-auto py-8">
        <p className="text-muted-foreground">{t("newVersion.loadingSkill")}</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8">
      {/* Header */}
      <div className="mb-6">
        <Link
          href={`/skills/${skillName}`}
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground mb-4"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          {t("newVersion.backTo", { name: skillName })}
        </Link>
        <h1 className="text-3xl font-bold">{t("newVersion.title")}</h1>
        <p className="text-muted-foreground mt-1">
          {t("newVersion.subtitle")}{" "}
          <span className="font-medium text-foreground">{skillName}</span>
          {skill?.current_version && (
            <span className="ml-2">{t("newVersion.currentVersion", { version: skill.current_version })}</span>
          )}
        </p>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Version Info */}
        <Card>
          <CardHeader>
            <CardTitle>{t("newVersion.versionInfo")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="version">
                  {t("newVersion.versionLabel")} <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="version"
                  placeholder={t("newVersion.versionPlaceholder")}
                  value={version}
                  onChange={(e) => {
                    setVersion(e.target.value);
                    setErrors((prev) => ({ ...prev, version: "" }));
                  }}
                  className={errors.version ? "border-destructive" : ""}
                />
                <p className="text-xs text-muted-foreground">
                  {t("newVersion.versionHelp")}
                </p>
                {errors.version && (
                  <p className="text-xs text-destructive">{errors.version}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="commit">{t("newVersion.commitMessage")}</Label>
                <Input
                  id="commit"
                  placeholder={t("newVersion.commitPlaceholder")}
                  value={commitMessage}
                  onChange={(e) => setCommitMessage(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  {t("newVersion.commitHelp")}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Content Tabs */}
        <Card>
          <CardHeader>
            <CardTitle>{t("newVersion.packageContent")}</CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="skill-md" className="space-y-4">
              <TabsList>
                <TabsTrigger value="skill-md">
                  SKILL.md <span className="text-destructive ml-1">*</span>
                </TabsTrigger>
                <TabsTrigger value="schema">schema.json</TabsTrigger>
                <TabsTrigger value="manifest">manifest.json</TabsTrigger>
              </TabsList>

              <TabsContent value="skill-md" className="space-y-2">
                <p className="text-sm text-muted-foreground">
                  {t("newVersion.skillMdDescription")}
                </p>
                <CodeEditor
                  value={skillMd}
                  onChange={setSkillMd}
                  language="markdown"
                  height="400px"
                />
                {errors.skillMd && (
                  <p className="text-xs text-destructive">{errors.skillMd}</p>
                )}
              </TabsContent>

              <TabsContent value="schema" className="space-y-2">
                <p className="text-sm text-muted-foreground">
                  {t("newVersion.schemaDescription")}
                </p>
                <CodeEditor
                  value={schemaJson}
                  onChange={setSchemaJson}
                  language="json"
                  height="300px"
                />
                {errors.schema && (
                  <p className="text-xs text-destructive">{errors.schema}</p>
                )}
              </TabsContent>

              <TabsContent value="manifest" className="space-y-2">
                <p className="text-sm text-muted-foreground">
                  {t("newVersion.manifestDescription")}
                </p>
                <CodeEditor
                  value={manifestJson}
                  onChange={setManifestJson}
                  language="json"
                  height="300px"
                />
                {errors.manifest && (
                  <p className="text-xs text-destructive">{errors.manifest}</p>
                )}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        {/* Submit Error */}
        {errors.submit && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-destructive">
            <p className="text-sm">{errors.submit}</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-4">
          <Button type="submit" disabled={createMutation.isPending}>
            {createMutation.isPending ? t("newVersion.creating") : t("newVersion.createButton")}
          </Button>
          <Button type="button" variant="outline" onClick={() => router.back()}>
            {tc("actions.cancel")}
          </Button>
        </div>
      </form>
    </div>
  );
}

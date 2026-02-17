"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { Spinner } from "@/components/ui/spinner";
import { skillsApi } from "@/lib/api";
import { useTranslation } from "@/i18n/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { SkillType } from "@/types/skill";

type CreationStatus = "idle" | "creating" | "polling" | "completed" | "failed";

export default function NewSkillPage() {
  const { t } = useTranslation("skills");
  const router = useRouter();
  const queryClient = useQueryClient();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [skillType, setSkillType] = useState<SkillType>("user");
  const [tagsInput, setTagsInput] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [status, setStatus] = useState<CreationStatus>("idle");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [traceId, setTraceId] = useState<string | null>(null);
  const [pollingMessage, setPollingMessage] = useState("");
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, []);

  const validateName = (value: string): string | null => {
    if (!value) return t("create.nameRequired");
    if (value.length < 2) return t("create.nameTooShort");
    if (value.length > 128) return t("create.nameTooLong");
    if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(value)) {
      return t("create.nameInvalid");
    }
    return null;
  };

  const pollTaskStatus = async (taskId: string) => {
    try {
      const result = await skillsApi.getTaskStatus(taskId);

      if (result.trace_id) {
        setTraceId(result.trace_id);
      }

      if (result.status === "completed") {
        setStatus("completed");
        if (pollingRef.current) {
          clearInterval(pollingRef.current);
        }
        queryClient.invalidateQueries({ queryKey: ["skills"] });
        router.push(`/skills/${name}`);
      } else if (result.status === "failed") {
        setStatus("failed");
        setErrors({ submit: result.error || t("create.creationFailed") });
        if (pollingRef.current) {
          clearInterval(pollingRef.current);
        }
      } else if (result.status === "running") {
        setPollingMessage(t("create.aiGenerating"));
      } else {
        setPollingMessage(t("create.startingCreation"));
      }
    } catch (error) {
      // Continue polling on network errors
      console.error("Polling error:", error);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const nameError = validateName(name);
    if (nameError) {
      setErrors({ name: nameError });
      return;
    }

    setErrors({});
    setStatus("creating");

    try {
      const parsedTags = tagsInput
        .split(",")
        .map((t) => t.trim().toLowerCase())
        .filter(Boolean);
      const result = await skillsApi.create({
        name,
        description: description || undefined,
        skill_type: skillType,
        tags: parsedTags.length > 0 ? parsedTags : undefined,
      });

      setTaskId(result.task_id);
      setStatus("polling");
      setPollingMessage(t("create.startingCreation"));

      // Start polling
      pollingRef.current = setInterval(() => {
        pollTaskStatus(result.task_id);
      }, 2000);

      // Initial poll
      pollTaskStatus(result.task_id);
    } catch (error) {
      setStatus("failed");
      setErrors({
        submit: error instanceof Error ? error.message : t("create.failedToStart"),
      });
    }
  };

  const isProcessing = status === "creating" || status === "polling";

  return (
    <div className="container mx-auto py-8 max-w-2xl">
      {/* Header */}
      <div className="mb-6">
        <Link
          href="/skills"
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground mb-4"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          {t("list.title")}
        </Link>
        <h1 className="text-3xl font-bold">{t("create.title")}</h1>
        <p className="text-muted-foreground mt-1">
          {t("create.subtitle")}
        </p>
      </div>

      {/* Form */}
      <Card>
        <CardHeader>
          <CardTitle>{t("create.skillDetails")}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Name */}
            <div className="space-y-2">
              <Label htmlFor="name">
                {t("create.name")} <span className="text-destructive">*</span>
              </Label>
              <Input
                id="name"
                placeholder={t("create.namePlaceholder")}
                value={name}
                onChange={(e) => {
                  setName(e.target.value.toLowerCase().replace(/\s+/g, "-"));
                  setErrors((prev) => ({ ...prev, name: "" }));
                }}
                className={errors.name ? "border-destructive" : ""}
                disabled={isProcessing}
              />
              <p className="text-xs text-muted-foreground">
                {t("create.nameHelp")}
              </p>
              {errors.name && (
                <p className="text-xs text-destructive">{errors.name}</p>
              )}
            </div>

            {/* Description */}
            <div className="space-y-2">
              <Label htmlFor="description">{t("create.description")}</Label>
              <Textarea
                id="description"
                placeholder={t("create.descriptionPlaceholder")}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                disabled={isProcessing}
              />
              <p className="text-xs text-muted-foreground">
                {t("create.descriptionHelp")}
              </p>
            </div>

            {/* Skill Type */}
            <div className="space-y-2">
              <Label htmlFor="skill-type">{t("create.skillType")}</Label>
              <Select
                value={skillType}
                onValueChange={(value: SkillType) => setSkillType(value)}
                disabled={isProcessing}
              >
                <SelectTrigger id="skill-type" className="w-[200px]">
                  <SelectValue placeholder={t("create.selectType")} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="user">{t("create.userSkill")}</SelectItem>
                  <SelectItem value="meta">{t("create.metaSkill")}</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                {t("create.skillTypeHelp")}
              </p>
            </div>

            {/* Tags */}
            <div className="space-y-2">
              <Label htmlFor="tags">{t("create.tags")}</Label>
              <Input
                id="tags"
                placeholder={t("create.tagsPlaceholder")}
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
                disabled={isProcessing}
              />
              <p className="text-xs text-muted-foreground">
                {t("create.tagsHelp")}
              </p>
            </div>

            {/* Submit Error */}
            {errors.submit && (
              <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-destructive">
                {errors.submit.includes("\nHint:") ? (
                  <>
                    <p className="text-sm">{errors.submit.split("\nHint:")[0]}</p>
                    <p className="text-xs mt-2 opacity-75">
                      {t("create.hint")}: {errors.submit.split("\nHint:")[1]}
                    </p>
                  </>
                ) : (
                  <p className="text-sm">{errors.submit}</p>
                )}
              </div>
            )}

            {/* Progress Message */}
            {isProcessing && (
              <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-blue-800 dark:bg-blue-950 dark:border-blue-800 dark:text-blue-200">
                <div className="flex items-center gap-2">
                  <Spinner size="sm" />
                  <p className="text-sm font-medium">{pollingMessage}</p>
                </div>
                {taskId && (
                  <p className="text-xs mt-2 font-mono text-blue-700 dark:text-blue-300">
                    {t("create.taskId")}: {taskId}
                  </p>
                )}
                {traceId && (
                  <a
                    href={`/traces/${traceId}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs mt-1 font-mono text-blue-700 dark:text-blue-300 hover:underline"
                  >
                    {t("create.viewTrace")}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                )}
                <p className="text-xs mt-2 text-blue-600 dark:text-blue-300">
                  {t("create.creationTime")}
                </p>
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-4">
              <Button type="submit" disabled={isProcessing}>
                {isProcessing ? (
                  <>
                    <Spinner size="sm" className="mr-2" />
                    {t("create.creating")}
                  </>
                ) : (
                  t("create.createButton")
                )}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => router.back()}
                disabled={isProcessing}
              >
                {t("create.cancel")}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Help */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-base">{t("create.whatHappensNext")}</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-2">
          <p>{t("create.whatHappensDescription")}</p>
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li>{t("create.step1")}</li>
            <li>{t("create.step2")}</li>
            <li>{t("create.step3")}</li>
            <li>{t("create.step4")}</li>
          </ul>
          <p className="mt-3 text-xs">
            {t("create.processTime")}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

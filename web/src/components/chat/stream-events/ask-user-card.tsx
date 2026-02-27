"use client";

import React from "react";
import { HelpCircle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Markdown } from "@/components/ui/markdown";
import type { AskUserData } from "@/types/stream-events";
import { useTranslation } from "@/i18n/client";

interface AskUserCardProps {
  data: AskUserData;
  onRespond?: (promptId: string, answer: string) => void;
  /** Pre-filled answer (inferred from next user message on session restore) */
  selectedAnswer?: string;
}

export function AskUserCard({ data, onRespond, selectedAnswer }: AskUserCardProps) {
  const { t } = useTranslation("chat");
  const [submitted, setSubmitted] = React.useState(!!selectedAnswer);
  const [localAnswer, setLocalAnswer] = React.useState(selectedAnswer || "");
  const inputRef = React.useRef<HTMLInputElement>(null);

  const handleSubmit = React.useCallback(
    (answer: string) => {
      if (!answer.trim() || submitted) return;
      setSubmitted(true);
      setLocalAnswer(answer.trim());
      onRespond?.(data.promptId, answer.trim());
    },
    [data.promptId, submitted, onRespond]
  );

  const displayAnswer = localAnswer;

  return (
    <div className="border border-amber-300 dark:border-amber-700 rounded-lg my-2 overflow-hidden bg-amber-50/50 dark:bg-amber-950/20">
      {/* Header */}
      <div className="flex items-start gap-2 px-3 py-2.5">
        <HelpCircle className="h-4 w-4 text-amber-600 dark:text-amber-400 mt-0.5 shrink-0" />
        <div className="text-sm text-foreground font-medium min-w-0 overflow-x-auto"><Markdown>{data.question}</Markdown></div>
      </div>

      {/* Answer area */}
      <div className="px-3 pb-3">
        {submitted ? (
          /* Answered state */
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <CheckCircle2 className="h-3.5 w-3.5 text-green-600 dark:text-green-400 shrink-0" />
            <span>
              {t("askUser.answered")}: <span className="font-medium text-foreground">{displayAnswer}</span>
            </span>
          </div>
        ) : data.options ? (
          /* Options mode: buttons */
          <div className="flex flex-wrap gap-2">
            {data.options.map((option) => (
              <Button
                key={option}
                variant="outline"
                size="sm"
                className="text-xs border-amber-300 dark:border-amber-700 hover:bg-amber-100 dark:hover:bg-amber-900/40"
                onClick={() => handleSubmit(option)}
              >
                {option}
              </Button>
            ))}
          </div>
        ) : (
          /* Free input mode */
          <div className="flex gap-2">
            <Input
              ref={inputRef}
              value={localAnswer}
              onChange={(e) => setLocalAnswer(e.target.value)}
              placeholder={t("askUser.typeAnswer")}
              className="text-sm h-8 border-amber-300 dark:border-amber-700"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(localAnswer);
                }
              }}
            />
            <Button
              size="sm"
              className="h-8 text-xs"
              onClick={() => handleSubmit(localAnswer)}
              disabled={!localAnswer.trim()}
            >
              {t("askUser.submit")}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

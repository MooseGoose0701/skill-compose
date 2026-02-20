"use client";

import { MessageSquare } from "lucide-react";
import type { SteeringReceivedData } from "@/types/stream-events";

interface SteeringMessageProps {
  data: SteeringReceivedData;
}

/**
 * Renders a user message sent while the agent is running.
 * Displayed as a compact right-aligned bubble (similar to a regular user message).
 */
export function SteeringMessage({ data }: SteeringMessageProps) {
  return (
    <div className="flex justify-end my-2">
      <div className="inline-flex items-start gap-2 max-w-[80%] rounded-lg bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 px-3 py-2 text-sm">
        <MessageSquare className="h-4 w-4 text-blue-500 mt-0.5 shrink-0" />
        <p className="text-foreground">{data.message}</p>
      </div>
    </div>
  );
}

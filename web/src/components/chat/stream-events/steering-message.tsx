"use client";

import { Navigation } from "lucide-react";
import type { SteeringReceivedData } from "@/types/stream-events";

interface SteeringMessageProps {
  data: SteeringReceivedData;
}

/**
 * Renders a steering message injected by the user during agent execution.
 * Displayed as a compact right-aligned bubble with a steering icon.
 */
export function SteeringMessage({ data }: SteeringMessageProps) {
  return (
    <div className="flex justify-end my-2">
      <div className="inline-flex items-start gap-2 max-w-[80%] rounded-lg bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 px-3 py-2 text-sm">
        <Navigation className="h-4 w-4 text-blue-500 mt-0.5 shrink-0" />
        <div>
          <span className="text-xs font-medium text-blue-600 dark:text-blue-400">Steering</span>
          <p className="text-foreground mt-0.5">{data.message}</p>
        </div>
      </div>
    </div>
  );
}

/**
 * Semantic Status Badge strictly following Warm Editorial Minimalism design.md.
 */

import React from "react";
import { cn } from "../../lib/utils";

export type StatusType =
  | "active"
  | "approved"
  | "succeeded"
  | "completed"
  | "ok"
  | "connected"
  | "delivered"
  | "pending"
  | "staging"
  | "flagged"
  | "warn"
  | "listening"
  | "reconnecting"
  | "quarantined"
  | "rejected"
  | "failed"
  | "expired"
  | "disconnected"
  | "error"
  | "archived"
  | "idle"
  | "standby"
  | "unknown"
  | "deprecated"
  | string;

interface StatusBadgeProps {
  status: StatusType;
  label?: string;
  size?: "sm" | "md";
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  label,
  size = "sm",
  className,
}) => {
  const norm = (status || "unknown").toLowerCase();

  let variantClasses = "bg-neutral-500/10 text-neutral-600 dark:text-neutral-400 border-neutral-300 dark:border-neutral-700";

  if (
    ["active", "approved", "succeeded", "completed", "ok", "connected", "delivered"].includes(norm)
  ) {
    variantClasses =
      "bg-teal-500/10 text-teal-800 dark:text-teal-300 border-teal-600/30";
  } else if (
    ["pending", "staging", "flagged", "warn", "listening", "reconnecting"].includes(norm)
  ) {
    variantClasses =
      "bg-amber-500/10 text-amber-800 dark:text-amber-300 border-amber-600/30";
  } else if (
    ["quarantined", "rejected", "failed", "expired", "disconnected", "error"].includes(norm)
  ) {
    variantClasses =
      "bg-rose-500/10 text-rose-800 dark:text-rose-300 border-rose-600/30";
  }

  const displayText = label || status;

  return (
    <span
      className={cn(
        "inline-flex items-center font-mono uppercase tracking-wider border",
        size === "sm" ? "px-1.5 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs",
        variantClasses,
        className
      )}
    >
      <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-current opacity-75" />
      {displayText}
    </span>
  );
};

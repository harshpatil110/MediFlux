/**
 * Editorial LLM & System Error Banner conforming to Warm Editorial Minimalism (design.md).
 * Displays normalized domain explanations, failover status, and actionable operator guidance.
 */

import React, { useState } from "react";
import { AlertCircle, AlertTriangle, ChevronDown, ChevronUp, Info, RefreshCw, X } from "lucide-react";
import { normalizeErrorMessage, type NormalizedError } from "../../lib/errorMessages";

interface LlmErrorBannerProps {
  error: unknown;
  onRetry?: () => void;
  onDismiss?: () => void;
  className?: string;
}

export const LlmErrorBanner: React.FC<LlmErrorBannerProps> = ({
  error,
  onRetry,
  onDismiss,
  className = "",
}) => {
  const [showDetails, setShowDetails] = useState(false);

  if (!error) return null;

  const normalized: NormalizedError = normalizeErrorMessage(error);
  const rawString = typeof error === "string" ? error : JSON.stringify(error, null, 2);

  const getBorderColor = () => {
    switch (normalized.severity) {
      case "critical":
        return "border-rose-500 bg-rose-50/70 text-rose-950 dark:bg-rose-950/40 dark:text-rose-100";
      case "error":
        return "border-coral-500 bg-amber-50/70 text-amber-950 dark:bg-amber-950/40 dark:text-amber-100";
      case "warning":
        return "border-amber-400 bg-amber-50/50 text-amber-900 dark:bg-amber-950/30 dark:text-amber-200";
      case "info":
      default:
        return "border-[var(--accent-teal)] bg-teal-50/50 text-teal-950 dark:bg-teal-950/30 dark:text-teal-100";
    }
  };

  const getIcon = () => {
    switch (normalized.severity) {
      case "critical":
      case "error":
        return <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0" />;
      case "warning":
        return <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />;
      case "info":
      default:
        return <Info className="w-4 h-4 text-[var(--accent-teal)] shrink-0" />;
    }
  };

  return (
    <div
      className={`border p-3.5 my-2.5 transition-all text-xs font-sans shadow-xs ${getBorderColor()} ${className}`}
      role="alert"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5 flex-1 min-w-0">
          <div className="mt-0.5">{getIcon()}</div>
          <div className="space-y-1 flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-serif font-bold tracking-tight text-xs">
                {normalized.title}
              </span>
              <span className="font-mono text-[10px] px-1.5 py-0.2 border border-current opacity-70">
                {normalized.code}
              </span>
            </div>
            <p className="leading-relaxed opacity-90">{normalized.message}</p>
            {normalized.actionableHint && (
              <p className="font-mono text-[11px] opacity-80 pt-0.5">
                ↳ <span className="font-semibold">Operator Action:</span> {normalized.actionableHint}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="p-1 hover:bg-black/10 dark:hover:bg-white/10 text-current transition-colors flex items-center gap-1 text-[11px] font-mono"
              title="Retry operation"
            >
              <RefreshCw className="w-3 h-3" />
              <span className="hidden sm:inline">Retry</span>
            </button>
          )}

          <button
            type="button"
            onClick={() => setShowDetails(!showDetails)}
            className="p-1 hover:bg-black/10 dark:hover:bg-white/10 text-current transition-colors"
            title="Toggle raw details"
          >
            {showDetails ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>

          {onDismiss && (
            <button
              type="button"
              onClick={onDismiss}
              className="p-1 hover:bg-black/10 dark:hover:bg-white/10 text-current transition-colors"
              title="Dismiss banner"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {showDetails && (
        <div className="mt-2.5 pt-2 border-t border-current/20">
          <pre className="font-mono text-[10px] p-2 bg-black/5 dark:bg-black/40 overflow-x-auto max-h-40 whitespace-pre-wrap break-all">
            {rawString}
          </pre>
        </div>
      )}
    </div>
  );
};

/**
 * Editorial LLM & System Error Banner conforming to Warm Editorial Minimalism (Design.md).
 * Displays normalized domain explanations, sovereign isolation status, and actionable operator guidance.
 * Strict adherence: 1px structural borders, Warm/Deep Ivory backgrounds, Ink Black / Charcoal typography.
 * Prohibitions: No circular pill-shaped buttons, no glassmorphism, no neon gradients, no dark mode defaults.
 */

import React, { useState } from "react";
import { AlertCircle, AlertTriangle, ChevronDown, ChevronUp, RefreshCw, ShieldAlert, X } from "lucide-react";
import { normalizeErrorMessage, type NormalizedError } from "../../lib/errorMessages";

export interface LlmErrorBannerProps {
  error: unknown;
  onRetry?: () => void;
  onDismiss?: () => void;
  variant?: "warning" | "error" | "sovereign";
  className?: string;
}

export const LlmErrorBanner: React.FC<LlmErrorBannerProps> = ({
  error,
  onRetry,
  onDismiss,
  variant,
  className = "",
}) => {
  const [showDetails, setShowDetails] = useState(false);

  if (!error) return null;

  const normalized: NormalizedError = normalizeErrorMessage(error);
  const activeVariant: "warning" | "error" | "sovereign" =
    variant || normalized.suggestedVariant || (normalized.code === "SOVEREIGN_LOCAL_MODEL_OFFLINE" ? "sovereign" : normalized.severity === "error" || normalized.severity === "critical" ? "error" : "warning");

  const rawString =
    typeof error === "string"
      ? error
      : error instanceof Error
      ? `${error.name}: ${error.message}${error.stack ? `\n${error.stack}` : ""}`
      : JSON.stringify(error, null, 2);

  // Styling maps strictly conforming to Warm Editorial Minimalism
  const getBannerStyles = () => {
    switch (activeVariant) {
      case "sovereign":
        return {
          container: "border border-[#00AEBB] bg-[#DFDBCA] text-[#031211]",
          badge: "border border-[#00AEBB] bg-[#00AEBB]/10 text-[#00AEBB]",
          icon: <ShieldAlert className="w-4 h-4 text-[#00AEBB] shrink-0" strokeWidth={1.5} />,
          tag: "SOVEREIGN LOCAL PRIVACY",
        };
      case "error":
        return {
          container: "border border-[#031211]/30 bg-[#DFDBCA] text-[#031211]",
          badge: "border border-[#031211]/20 bg-[#E8E4D3] text-[#031211]",
          icon: <AlertCircle className="w-4 h-4 text-[#031211] shrink-0" strokeWidth={1.5} />,
          tag: "CRITICAL INCIDENT",
        };
      case "warning":
      default:
        return {
          container: "border border-[#D8D3C3] bg-[#E8E4D3] text-[#031211]",
          badge: "border border-[#D8D3C3] bg-[#DFDBCA] text-[#5C584E]",
          icon: <AlertTriangle className="w-4 h-4 text-[#5C584E] shrink-0" strokeWidth={1.5} />,
          tag: "OPERATIONAL NOTICE",
        };
    }
  };

  const styles = getBannerStyles();

  return (
    <div
      className={`p-4 my-3 text-xs font-sans shadow-sm transition-all rounded-sm ${styles.container} ${className}`}
      role="alert"
    >
      <div className="flex items-start justify-between gap-3">
        {/* Left: Icon & Details */}
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="mt-0.5">{styles.icon}</div>
          <div className="space-y-1.5 flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-serif font-bold text-sm tracking-tight text-[#031211]">
                {normalized.title}
              </span>
              <span className={`font-mono text-[10px] px-1.5 py-0.5 rounded-none font-medium uppercase tracking-wider ${styles.badge}`}>
                {styles.tag}
              </span>
              <span className="font-mono text-[10px] px-1.5 py-0.5 border border-[#D8D3C3] bg-[#E8E4D3] text-[#5C584E]">
                {normalized.code}
              </span>
            </div>

            <p className="leading-relaxed text-[#5C584E] text-xs">
              {normalized.message}
            </p>

            {normalized.actionableHint && (
              <p className="font-mono text-[11px] text-[#031211] pt-1 border-t border-[#D8D3C3]/60">
                <span className="font-semibold uppercase tracking-wider text-[10px] text-[#5C584E]">Operator Action:</span>{" "}
                {normalized.actionableHint}
              </p>
            )}
          </div>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-1.5 shrink-0 ml-2">
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="px-2.5 py-1 text-xs font-mono border border-[#C5C0B0] bg-[#E8E4D3] hover:bg-[#DFDBCA] text-[#031211] rounded-sm transition-colors flex items-center gap-1.5"
              title="Retry operation"
            >
              <RefreshCw className="w-3 h-3 text-[#00AEBB]" strokeWidth={1.5} />
              <span>Retry</span>
            </button>
          )}

          <button
            type="button"
            onClick={() => setShowDetails(!showDetails)}
            className="p-1 border border-[#C5C0B0] bg-[#E8E4D3] hover:bg-[#DFDBCA] text-[#5C584E] hover:text-[#031211] rounded-sm transition-colors"
            title="Toggle raw error trace"
          >
            {showDetails ? (
              <ChevronUp className="w-3.5 h-3.5" strokeWidth={1.5} />
            ) : (
              <ChevronDown className="w-3.5 h-3.5" strokeWidth={1.5} />
            )}
          </button>

          {onDismiss && (
            <button
              type="button"
              onClick={onDismiss}
              className="p-1 border border-[#C5C0B0] bg-[#E8E4D3] hover:bg-[#DFDBCA] text-[#5C584E] hover:text-[#031211] rounded-sm transition-colors"
              title="Dismiss banner"
            >
              <X className="w-3.5 h-3.5" strokeWidth={1.5} />
            </button>
          )}
        </div>
      </div>

      {/* Raw Trace Accordion */}
      {showDetails && (
        <div className="mt-3 pt-2.5 border-t border-[#D8D3C3]">
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#5C584E] mb-1">
            Raw Diagnostics
          </div>
          <pre className="font-mono text-[10px] p-2.5 bg-[#E8E4D3] border border-[#D8D3C3] text-[#031211] overflow-x-auto max-h-48 whitespace-pre-wrap break-all rounded-none">
            {rawString}
          </pre>
        </div>
      )}
    </div>
  );
};

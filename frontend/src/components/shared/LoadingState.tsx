/**
 * Loading state indicator styled for Warm Editorial Minimalism.
 */

import React from "react";
import { RefreshCw } from "lucide-react";

interface LoadingStateProps {
  message?: string;
  className?: string;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = "Loading data from network...",
  className = "py-16",
}) => {
  return (
    <div className={`flex flex-col items-center justify-center gap-3 ${className}`}>
      <RefreshCw className="w-5 h-5 text-[var(--accent-teal)] animate-spin" />
      <span className="text-xs font-mono uppercase tracking-widest text-[var(--text-secondary)]">
        {message}
      </span>
    </div>
  );
};

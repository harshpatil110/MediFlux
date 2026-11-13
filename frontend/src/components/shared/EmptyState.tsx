/**
 * Empty state fallback for tables and lists.
 */

import React from "react";
import { Inbox } from "lucide-react";

interface EmptyStateProps {
  icon?: React.ComponentType<{ className?: string }>;
  title?: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon: Icon = Inbox,
  title = "No records found",
  description = "No items match your active filters or query parameters.",
  action,
  className = "py-12",
}) => {
  return (
    <div className={`flex flex-col items-center justify-center text-center p-6 ${className}`}>
      <div className="w-10 h-10 mb-3 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] flex items-center justify-center text-[var(--text-secondary)]">
        <Icon className="w-5 h-5" />
      </div>
      <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-1">
        {title}
      </h3>
      <p className="text-xs text-[var(--text-secondary)] max-w-sm mb-4 leading-relaxed">
        {description}
      </p>
      {action && (
        <button
          type="button"
          onClick={action.onClick}
          className="px-3 py-1.5 text-xs font-medium bg-[var(--accent-teal)] text-white hover:bg-[var(--accent-teal)]/90 transition-colors"
        >
          {action.label}
        </button>
      )}
    </div>
  );
};

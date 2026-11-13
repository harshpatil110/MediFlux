/**
 * Monospace JSON inspector with collapsible view and one-click copy.
 */

import React, { useState } from "react";
import { Check, Copy, ChevronDown, ChevronRight } from "lucide-react";

interface JsonViewerProps {
  data: any;
  title?: string;
  defaultExpanded?: boolean;
  maxHeight?: string;
}

export const JsonViewer: React.FC<JsonViewerProps> = ({
  data,
  title,
  defaultExpanded = true,
  maxHeight = "360px",
}) => {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [copied, setCopied] = useState(false);

  const jsonString = typeof data === "string" ? data : JSON.stringify(data, null, 2);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(jsonString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="border border-[var(--border-subtle)] bg-[var(--bg-canvas)] font-mono text-xs overflow-hidden">
      <div
        onClick={() => setExpanded(!expanded)}
        className="px-3 py-2 bg-[var(--bg-surface)] border-b border-[var(--border-subtle)] flex items-center justify-between cursor-pointer select-none"
      >
        <div className="flex items-center gap-2 text-[var(--text-primary)]">
          {expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          <span className="font-semibold">{title || "JSON Payload"}</span>
          <span className="text-[10px] text-[var(--text-secondary)]">
            ({typeof data === "object" && data !== null ? `${Object.keys(data).length} fields` : "raw"})
          </span>
        </div>
        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] border border-[var(--border-subtle)] hover:bg-[var(--bg-canvas)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        >
          {copied ? (
            <>
              <Check className="w-3 h-3 text-teal-600" /> Copied
            </>
          ) : (
            <>
              <Copy className="w-3 h-3" /> Copy JSON
            </>
          )}
        </button>
      </div>

      {expanded && (
        <div className="p-3 overflow-auto text-[var(--text-primary)] leading-relaxed" style={{ maxHeight }}>
          <pre className="whitespace-pre font-mono text-[11px] leading-tight">
            {jsonString}
          </pre>
        </div>
      )}
    </div>
  );
};

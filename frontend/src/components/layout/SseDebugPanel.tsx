/**
 * Docked Live SSE Debug Panel allowing real-time event inspection and live test event emission.
 */

import React, { useState } from "react";
import {
  Activity,
  X,
  Play,
  Trash2,
  RefreshCw,
  Radio,
} from "lucide-react";
import { useEventStream } from "../../hooks/useEventStream";
import { api } from "../../lib/api";
import { StatusBadge } from "../shared/StatusBadge";
import { JsonViewer } from "../shared/JsonViewer";

interface SseDebugPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

const AVAILABLE_TOPICS = [
  { id: "*", label: "All Topics (*)" },
  { id: "pos.sales", label: "pos.sales" },
  { id: "cascade.updates", label: "cascade.updates" },
  { id: "agent.activity", label: "agent.activity" },
  { id: "hitl", label: "hitl" },
  { id: "coldchain", label: "coldchain" },
  { id: "regulatory", label: "regulatory" },
];

export const SseDebugPanel: React.FC<SseDebugPanelProps> = ({ isOpen, onClose }) => {
  const [selectedTopic, setSelectedTopic] = useState<string>("*");
  const [isEmitting, setIsEmitting] = useState<boolean>(false);
  const [emitStatus, setEmitStatus] = useState<string | null>(null);

  const { events, connectionState, lastEventId, clearEvents, reconnect } = useEventStream({
    topics: selectedTopic === "*" ? ["*"] : [selectedTopic],
    enabled: isOpen,
  });

  const handleEmitTestEvent = async () => {
    setIsEmitting(true);
    setEmitStatus(null);
    try {
      const now = new Date();
      const testPayload = {
        type: selectedTopic === "*" ? "pos.sales" : selectedTopic,
        event_id: `test-evt-${Date.now()}`,
        node_id: "11111111-1111-1111-1111-111111111111",
        pharmacy_id: "11111111-1111-1111-1111-111111111111",
        product_id: "00000000-0000-0000-0000-000000000001",
        batch_id: "BATCH-TEST-01",
        quantity: 1,
        source: "sse_debug_panel",
        timestamp: now.toISOString(),
        payload: {
          test: true,
          emitted_from: "SseDebugPanel",
          note: "Live retail dispense simulation trigger",
          timestamp: now.toISOString(),
        },
      };

      await api.events.postEvent(testPayload);
      setEmitStatus("Dispatched!");
      setTimeout(() => setEmitStatus(null), 3000);
    } catch (err: any) {
      setEmitStatus(`Error: ${err.message || "Failed"}`);
      setTimeout(() => setEmitStatus(null), 4000);
    } finally {
      setIsEmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-xl bg-[var(--bg-surface)] border-l border-[var(--border-subtle)] shadow-2xl flex flex-col transition-transform duration-200">
      {/* Header */}
      <div className="px-5 py-4 border-b border-[var(--border-subtle)] flex items-center justify-between bg-[var(--bg-canvas)]">
        <div className="flex items-center gap-3">
          <div className="p-1.5 border border-[var(--border-subtle)] bg-[var(--bg-surface)]">
            <Radio className="w-4 h-4 text-[var(--accent-teal)]" />
          </div>
          <div>
            <h2 className="text-sm font-serif font-bold text-[var(--text-primary)]">
              Live SSE Stream Telemetry
            </h2>
            <div className="flex items-center gap-2 text-[10px] font-mono mt-0.5">
              <span className="text-[var(--text-secondary)]">Status:</span>
              <StatusBadge status={connectionState} size="sm" />
              {lastEventId && (
                <span className="text-[var(--text-secondary)]">
                  Last ID: <span className="text-[var(--text-primary)] font-semibold">{lastEventId.slice(-8)}</span>
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={reconnect}
            title="Reconnect stream"
            className="p-1.5 border border-[var(--border-subtle)] hover:bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 border border-[var(--border-subtle)] hover:bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Control Bar: Topics & Actions */}
      <div className="p-4 border-b border-[var(--border-subtle)] bg-[var(--bg-surface)] space-y-3">
        {/* Topic Filter Chips */}
        <div>
          <span className="text-[10px] font-mono uppercase tracking-widest text-[var(--text-secondary)] block mb-1.5">
            Filter Topic:
          </span>
          <div className="flex flex-wrap gap-1.5">
            {AVAILABLE_TOPICS.map((topic) => (
              <button
                key={topic.id}
                type="button"
                onClick={() => setSelectedTopic(topic.id)}
                className={`px-2 py-0.5 text-[11px] font-mono border transition-colors ${
                  selectedTopic === topic.id
                    ? "bg-[var(--accent-teal)] text-white border-[var(--accent-teal)] font-medium"
                    : "bg-[var(--bg-canvas)] text-[var(--text-secondary)] border-[var(--border-subtle)] hover:text-[var(--text-primary)]"
                }`}
              >
                {topic.label}
              </button>
            ))}
          </div>
        </div>

        {/* Action Triggers */}
        <div className="flex items-center justify-between pt-1">
          <button
            type="button"
            onClick={handleEmitTestEvent}
            disabled={isEmitting}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[var(--accent-teal)] text-white hover:bg-[var(--accent-teal)]/90 transition-colors disabled:opacity-50"
          >
            {isEmitting ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Play className="w-3.5 h-3.5" />
            )}
            Emit Live Test Event
          </button>

          {emitStatus && (
            <span className="text-xs font-mono text-teal-600 dark:text-teal-400 font-medium">
              {emitStatus}
            </span>
          )}

          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono text-[var(--text-secondary)]">
              {events.length} buffered
            </span>
            <button
              type="button"
              onClick={clearEvents}
              disabled={events.length === 0}
              className="p-1 border border-[var(--border-subtle)] hover:bg-[var(--bg-canvas)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors disabled:opacity-30"
              title="Clear events buffer"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Events Feed Container */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-[var(--bg-canvas)]">
        {events.length === 0 ? (
          <div className="h-64 flex flex-col items-center justify-center text-center text-[var(--text-secondary)]">
            <Activity className="w-8 h-8 opacity-30 mb-2" />
            <p className="text-xs font-mono">Awaiting live events on stream...</p>
            <p className="text-[11px] mt-1 opacity-70">
              Click &quot;Emit Live Test Event&quot; above to publish an event.
            </p>
          </div>
        ) : (
          events.map((evt) => (
            <div
              key={evt.event_id}
              className="p-3 bg-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-sm space-y-2"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <StatusBadge status="active" label={evt.type} size="sm" />
                  <span className="text-[11px] font-mono font-medium text-[var(--text-primary)]">
                    {evt.event_id.slice(0, 16)}...
                  </span>
                </div>
                <span className="text-[10px] font-mono text-[var(--text-secondary)]">
                  {new Date(evt.timestamp).toLocaleTimeString()}
                </span>
              </div>

              {evt.correlation_id && (
                <div className="text-[10px] font-mono text-[var(--text-secondary)] truncate">
                  corr: {evt.correlation_id}
                </div>
              )}

              <JsonViewer
                data={evt.payload}
                title="Event Payload"
                defaultExpanded={false}
                maxHeight="180px"
              />
            </div>
          ))
        )}
      </div>
    </div>
  );
};

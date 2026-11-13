/**
 * Network Copilot & Semantic Vector Search Screen (/copilot)
 *
 * Implements Task 21 & Task 27:
 * - Caller RLS Scope indicator (Pharmacy node vs Network Admin).
 * - Suggested operational questions quick-chips.
 * - Conversational interface with tool execution progress pills (tools_used).
 * - Grounded multi-entity reference chips linking to /overview, /regulatory-lab, /cold-chain, /approvals, /cascade.
 * - Integrated pgvector semantic search tab (GET /api/v1/search?q=).
 */

import React, { useState } from "react";
import { Link } from "react-router-dom";
import {
  Bot,
  BrainCircuit,
  Database,
  ExternalLink,
  Layers,
  MessageSquare,
  RefreshCw,
  Search,
  Send,
  Sparkles,
  User,
  Wrench,
} from "lucide-react";
import { api, getStoredUser } from "../lib/api";
import type { CopilotQueryReference, CopilotQueryResponseDetailed, SearchResult } from "../types/api";

interface ChatMessage {
  id: string;
  sender: "user" | "copilot";
  text: string;
  tools_used?: string[];
  references?: CopilotQueryReference[];
  trace_id?: string;
  timestamp: string;
}

const SUGGESTED_QUESTIONS = [
  "What is the real-time stock balance of Amoxicillin 500mg across all nodes?",
  "Are there any active cold-chain excursions or quarantined vaccine batches?",
  "Summarize the recent CDSCO DPCO ceiling price updates on Azithromycin.",
  "Show open HITL approval tasks requiring dual pharmacist authorization.",
  "Explain the automated demand cascade restock flow from retail to plant.",
];

export const CopilotPage: React.FC = () => {
  const currentUser = getStoredUser();
  const isPharmacyRole = currentUser?.role === "pharmacy";

  const [activeTab, setActiveTab] = useState<"chat" | "search">("chat");
  const [inputText, setInputText] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  // Chat message state
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome-1",
      sender: "copilot",
      text: "Greetings. I am the MediFlux Network Copilot, grounded in live multi-tier supply chain state, CDSCO regulatory gazettes, and real-time IoT cold-chain telemetry. How may I assist your operations today?",
      tools_used: ["knowledge_base", "rls_guard"],
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    },
  ]);

  // Semantic search state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  // Handle Copilot Query
  const handleSendMessage = async (queryToRun?: string) => {
    const text = (queryToRun || inputText).trim();
    if (!text || isLoading) return;

    const userMsg: ChatMessage = {
      id: `usr-${Date.now()}`,
      sender: "user",
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText("");
    setIsLoading(true);

    try {
      const res: CopilotQueryResponseDetailed = await api.copilot.query({
        question: text,
      });

      const copilotMsg: ChatMessage = {
        id: `cpl-${Date.now()}`,
        sender: "copilot",
        text: res.answer,
        tools_used: res.tools_used || [],
        references: res.references || [],
        trace_id: res.trace_id,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };

      setMessages((prev) => [...prev, copilotMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        sender: "copilot",
        text: `Query failed: ${err.message || "An operational error occurred while evaluating your question."}`,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  // Handle Semantic Vector Search
  const handleSemanticSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = searchQuery.trim();
    if (!q || isSearching) return;

    setIsSearching(true);
    setHasSearched(true);
    try {
      const res = await api.copilot.search(q, undefined, 10);
      setSearchResults(res.results || []);
    } catch (err) {
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  // Helper to map reference entity type to destination UI route
  const getReferenceLink = (ref: CopilotQueryReference): { path: string; label: string } => {
    const entity = (ref.entity_type || "").toLowerCase();
    if (entity.includes("regulatory") || entity.includes("gazette")) {
      return { path: "/regulatory-lab", label: "View in Regulatory Lab" };
    }
    if (entity.includes("coldchain") || entity.includes("batch")) {
      return { path: "/cold-chain", label: "View Cold-Chain Batch" };
    }
    if (entity.includes("hitl") || entity.includes("approval")) {
      return { path: "/approvals", label: "Inspect in Approvals" };
    }
    if (entity.includes("cascade") || entity.includes("run") || entity.includes("agent")) {
      return { path: "/cascade", label: "View Demand Cascade" };
    }
    return { path: "/overview", label: "View in Network Overview" };
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* 1. Header with Caller RLS Scope Indicator */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[var(--border-subtle)] pb-4">
        <div>
          <h2 className="text-xl font-serif font-bold text-[var(--text-primary)] flex items-center gap-2">
            <BrainCircuit className="w-5 h-5 text-[var(--accent-teal)]" />
            Network Copilot & Semantic Knowledge Retrieval
          </h2>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Grounded operational intelligence synthesized across live inventory balances, cold-chain telemetry, CDSCO DPCO rules, and demand cascades.
          </p>
        </div>

        {/* Caller RLS Scope Badge */}
        <div className="flex items-center gap-2 p-2 bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-xs font-mono">
          <span className="text-[var(--text-secondary)]">Operational Scope:</span>
          {isPharmacyRole ? (
            <span className="px-2 py-0.5 font-bold bg-amber-100 text-amber-900 border border-amber-300 dark:bg-amber-950/60 dark:text-amber-200">
              PHARMACY NODE (RLS BOUND)
            </span>
          ) : (
            <span className="px-2 py-0.5 font-bold bg-teal-100 text-teal-900 border border-[var(--accent-teal)] dark:bg-teal-950/60 dark:text-teal-200">
              NETWORK ADMIN (FULL TOPOLOGY)
            </span>
          )}
        </div>
      </div>

      {/* 2. Top Mode Switcher Tabs */}
      <div className="flex border-b border-[var(--border-subtle)] gap-2">
        <button
          type="button"
          onClick={() => setActiveTab("chat")}
          className={`px-4 py-2 text-xs font-mono uppercase tracking-wider font-semibold border-b-2 transition-all flex items-center gap-2 ${
            activeTab === "chat"
              ? "border-[var(--accent-teal)] text-[var(--accent-teal)] bg-[var(--bg-surface)]"
              : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
        >
          <MessageSquare className="w-3.5 h-3.5" />
          Conversational Copilot
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("search")}
          className={`px-4 py-2 text-xs font-mono uppercase tracking-wider font-semibold border-b-2 transition-all flex items-center gap-2 ${
            activeTab === "search"
              ? "border-[var(--accent-teal)] text-[var(--accent-teal)] bg-[var(--bg-surface)]"
              : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
        >
          <Search className="w-3.5 h-3.5" />
          pgvector Semantic Search
        </button>
      </div>

      {/* 3. TAB 1: Conversational Copilot Chat */}
      {activeTab === "chat" && (
        <div className="space-y-4">
          {/* Suggested Questions Quick-Chips */}
          <div className="p-3.5 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-2">
            <span className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-secondary)] block font-semibold flex items-center gap-1.5">
              <Sparkles className="w-3 h-3 text-[var(--accent-teal)]" />
              Suggested Operational Inquiries:
            </span>
            <div className="flex flex-wrap gap-2">
              {SUGGESTED_QUESTIONS.map((q, idx) => (
                <button
                  key={idx}
                  type="button"
                  disabled={isLoading}
                  onClick={() => handleSendMessage(q)}
                  className="px-2.5 py-1 text-xs font-mono border border-[var(--border-subtle)] bg-[var(--bg-canvas)] hover:border-[var(--accent-teal)] hover:text-[var(--accent-teal)] text-[var(--text-secondary)] transition-all text-left disabled:opacity-50"
                >
                  "{q}"
                </button>
              ))}
            </div>
          </div>

          {/* Chat Transcript Container */}
          <div className="p-4 bg-[var(--bg-surface)] border border-[var(--border-subtle)] min-h-[460px] max-h-[620px] overflow-y-auto space-y-5">
            {messages.map((msg) => {
              const isCopilot = msg.sender === "copilot";
              return (
                <div
                  key={msg.id}
                  className={`flex gap-3 max-w-3xl ${isCopilot ? "mr-auto" : "ml-auto flex-row-reverse"}`}
                >
                  {/* Avatar */}
                  <div
                    className={`w-7 h-7 shrink-0 flex items-center justify-center border text-xs font-mono ${
                      isCopilot
                        ? "bg-[var(--accent-teal)]/10 text-[var(--accent-teal)] border-[var(--accent-teal)]/40"
                        : "bg-[var(--bg-canvas)] text-[var(--text-primary)] border-[var(--border-subtle)]"
                    }`}
                  >
                    {isCopilot ? <Bot className="w-4 h-4" /> : <User className="w-4 h-4" />}
                  </div>

                  {/* Message Bubble */}
                  <div className="space-y-2 flex-1">
                    <div
                      className={`p-3.5 border text-xs font-mono leading-relaxed space-y-2 ${
                        isCopilot
                          ? "bg-[var(--bg-canvas)] border-[var(--border-subtle)] text-[var(--text-primary)]"
                          : "bg-[var(--accent-teal)] text-[var(--bg-surface)] font-semibold border-[var(--accent-teal)]"
                      }`}
                    >
                      <div className="whitespace-pre-wrap">{msg.text}</div>

                      {/* Tool selection pills (for Copilot responses) */}
                      {isCopilot && msg.tools_used && msg.tools_used.length > 0 && (
                        <div className="pt-2 border-t border-[var(--border-subtle)] flex flex-wrap items-center gap-1.5 text-[10px]">
                          <span className="text-[var(--text-secondary)] flex items-center gap-1">
                            <Wrench className="w-3 h-3 text-[var(--accent-teal)]" />
                            Grounded Tools Executed:
                          </span>
                          {msg.tools_used.map((tool, tIdx) => (
                            <span
                              key={tIdx}
                              className="px-1.5 py-0.2 bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-[var(--text-secondary)] font-mono"
                            >
                              {tool}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Interactive Multi-Entity Reference Chips */}
                    {isCopilot && msg.references && msg.references.length > 0 && (
                      <div className="space-y-1.5 pl-1">
                        <span className="text-[10px] font-mono text-[var(--text-secondary)] uppercase tracking-wider block">
                          Grounded Citations & Direct Navigation:
                        </span>
                        <div className="flex flex-wrap gap-2">
                          {msg.references.map((ref, rIdx) => {
                            const { path, label } = getReferenceLink(ref);
                            return (
                              <Link
                                key={rIdx}
                                to={path}
                                className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-[var(--bg-canvas)] hover:bg-[var(--bg-surface)] border border-[var(--border-subtle)] hover:border-[var(--accent-teal)] text-xs font-mono text-[var(--text-primary)] transition-all shadow-2xs group"
                              >
                                <ExternalLink className="w-3 h-3 text-[var(--accent-teal)] group-hover:translate-x-0.5 transition-transform" />
                                <span>{ref.title || label}</span>
                                <span className="text-[10px] text-[var(--text-secondary)] uppercase">
                                  ({ref.entity_type || "entity"})
                                </span>
                              </Link>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    <div className="text-[10px] font-mono text-[var(--text-secondary)] px-1">
                      {msg.timestamp} {msg.trace_id && `• Trace: ${msg.trace_id.slice(0, 8)}...`}
                    </div>
                  </div>
                </div>
              );
            })}

            {isLoading && (
              <div className="flex items-center gap-3 p-3 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-xs font-mono text-[var(--text-secondary)] max-w-md">
                <RefreshCw className="w-4 h-4 text-[var(--accent-teal)] animate-spin" />
                <span>Invoking grounded tools, validating caller RLS, synthesizing answer...</span>
              </div>
            )}
          </div>

          {/* Chat Input Bar */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Ask Copilot about supply chain bottlenecks, DPCO gazettes, or cold-chain integrity..."
              disabled={isLoading}
              className="flex-1 px-4 py-2.5 text-xs font-mono bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-[var(--text-primary)] placeholder-[var(--text-secondary)] focus:outline-none focus:border-[var(--accent-teal)] transition-colors"
            />
            <button
              type="submit"
              disabled={isLoading || !inputText.trim()}
              className="px-5 py-2.5 bg-[var(--accent-teal)] hover:opacity-90 disabled:opacity-50 text-[var(--bg-surface)] font-mono text-xs uppercase tracking-wider font-semibold flex items-center gap-1.5 transition-all"
            >
              <Send className="w-3.5 h-3.5" /> Send
            </button>
          </form>
        </div>
      )}

      {/* 4. TAB 2: pgvector Semantic Search */}
      {activeTab === "search" && (
        <div className="p-5 bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-5">
          <div>
            <h3 className="text-sm font-serif font-bold text-[var(--text-primary)] flex items-center gap-2">
              <Database className="w-4 h-4 text-[var(--accent-teal)]" />
              pgvector Cosine-Similarity Semantic Search
            </h3>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              Query vectorized pharmaceutical knowledge embeddings (products, gazette regulations, cold-chain telemetry breaches, and agent event logs).
            </p>
          </div>

          {/* Search Form */}
          <form onSubmit={handleSemanticSearch} className="flex gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Enter semantic query e.g. 'DPCO ceiling price cap on Amoxicillin' or 'thermal excursion vaccine'..."
              className="flex-1 px-4 py-2 text-xs font-mono bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-teal)]"
            />
            <button
              type="submit"
              disabled={isSearching || !searchQuery.trim()}
              className="px-4 py-2 bg-[var(--accent-teal)] text-[var(--bg-surface)] font-mono text-xs uppercase tracking-wider font-semibold flex items-center gap-1.5 hover:opacity-90 disabled:opacity-50"
            >
              {isSearching ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
              Vector Search
            </button>
          </form>

          {/* Results List */}
          <div className="space-y-3">
            {isSearching ? (
              <div className="p-8 text-center text-xs font-mono text-[var(--text-secondary)]">
                Computing cosine similarity embeddings over pgvector index...
              </div>
            ) : hasSearched && searchResults.length === 0 ? (
              <div className="p-8 text-center text-xs text-[var(--text-secondary)] bg-[var(--bg-canvas)] border border-[var(--border-subtle)]">
                No matching semantic embeddings discovered for "{searchQuery}".
              </div>
            ) : (
              searchResults.map((res) => (
                <div
                  key={res.id}
                  className="p-3.5 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] space-y-1.5 hover:border-[var(--accent-teal)] transition-all"
                >
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
                      <Layers className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
                      {res.category.toUpperCase()} • ID: {res.id}
                    </span>
                    <span className="px-1.5 py-0.2 text-[10px] bg-teal-50 text-teal-800 border border-teal-200 dark:bg-teal-950/40 dark:text-teal-300">
                      Similarity: {(res.similarity * 100).toFixed(1)}%
                    </span>
                  </div>

                  <p className="text-xs text-[var(--text-primary)] leading-relaxed font-mono">{res.content}</p>

                  {res.metadata && (
                    <div className="text-[10px] font-mono text-[var(--text-secondary)] pt-1 border-t border-[var(--border-subtle)] flex flex-wrap gap-3">
                      {Object.entries(res.metadata).map(([k, v]) => (
                        <span key={k}>
                          {k}: <code className="text-[var(--text-primary)]">{String(v)}</code>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};

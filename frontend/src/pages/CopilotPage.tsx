/**
 * Network Copilot Page (/copilot)
 * RLS-scoped conversational supply chain query engine and pgvector semantic search.
 */

import React, { useState } from "react";
import { BookOpen, Bot, RefreshCw, Send, Sparkles, User } from "lucide-react";
import { api } from "../lib/api";
import type { CopilotQueryResponse } from "../types/api";

interface Message {
  id: string;
  sender: "user" | "copilot";
  text: string;
  citations?: Array<{ source: string; content: string; confidence?: number }>;
  timestamp: string;
}

export const CopilotPage: React.FC = () => {
  const [queryText, setQueryText] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome-1",
      sender: "copilot",
      text: "Greetings. I am the MediFlux Network Copilot. You may ask me about network inventory, cold-chain status, CDSCO regulatory gazettes, or demand cascade propagation.",
      timestamp: new Date().toLocaleTimeString(),
    },
  ]);
  const [isLoading, setIsLoading] = useState(false);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!queryText.trim() || isLoading) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      sender: "user",
      text: queryText,
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setQueryText("");
    setIsLoading(true);

    try {
      const response: CopilotQueryResponse = await api.copilot.query(userMessage.text);
      const copilotMessage: Message = {
        id: `copilot-${Date.now()}`,
        sender: "copilot",
        text: response.answer || "No response generated.",
        citations: response.citations,
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, copilotMessage]);
    } catch (err: any) {
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        sender: "copilot",
        text: `Error processing query: ${err.message || "Backend request failed"}`,
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto h-[calc(100vh-140px)] flex flex-col">
      {/* Top Banner */}
      <div className="flex items-center justify-between pb-3 border-b border-[var(--border-subtle)]">
        <div>
          <h2 className="text-xl font-serif font-bold text-[var(--text-primary)] flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-[var(--accent-teal)]" />
            Network Copilot & Semantic Intelligence
          </h2>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Grounded RLS-scoped conversational AI assistant backed by pgvector semantic embeddings.
          </p>
        </div>
      </div>

      {/* Messages Thread Container */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-2">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 max-w-3xl ${
              msg.sender === "user" ? "ml-auto flex-row-reverse" : "mr-auto"
            }`}
          >
            <div
              className={`w-8 h-8 border border-[var(--border-subtle)] flex items-center justify-center shrink-0 ${
                msg.sender === "user"
                  ? "bg-[var(--accent-teal)] text-white"
                  : "bg-[var(--bg-surface)] text-[var(--accent-teal)]"
              }`}
            >
              {msg.sender === "user" ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
            </div>

            <div
              className={`p-4 border text-xs leading-relaxed space-y-2.5 ${
                msg.sender === "user"
                  ? "bg-[var(--accent-teal)]/10 border-[var(--accent-teal)]/30 text-[var(--text-primary)]"
                  : "bg-[var(--bg-surface)] border-[var(--border-subtle)] text-[var(--text-primary)]"
              }`}
            >
              <div className="flex items-center justify-between text-[10px] font-mono opacity-70">
                <span className="font-semibold uppercase">
                  {msg.sender === "user" ? "You" : "MediFlux Copilot"}
                </span>
                <span>{msg.timestamp}</span>
              </div>

              <p className="whitespace-pre-wrap">{msg.text}</p>

              {msg.citations && msg.citations.length > 0 && (
                <div className="pt-2 border-t border-[var(--border-subtle)] space-y-1.5">
                  <span className="text-[10px] font-mono uppercase tracking-widest text-[var(--text-secondary)] flex items-center gap-1">
                    <BookOpen className="w-3 h-3 text-[var(--accent-teal)]" />
                    Grounded Citations ({msg.citations.length}):
                  </span>
                  <div className="space-y-1">
                    {msg.citations.map((c, idx) => (
                      <div
                        key={idx}
                        className="p-2 bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[11px] font-mono text-[var(--text-secondary)]"
                      >
                        <span className="font-semibold text-[var(--text-primary)]">[{c.source}]</span>:{" "}
                        {c.content}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex gap-3 max-w-3xl mr-auto items-center">
            <div className="w-8 h-8 border border-[var(--border-subtle)] bg-[var(--bg-surface)] flex items-center justify-center text-[var(--accent-teal)]">
              <RefreshCw className="w-4 h-4 animate-spin" />
            </div>
            <div className="p-3 bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-xs font-mono text-[var(--text-secondary)]">
              Consulting semantic vector database and supply chain graph...
            </div>
          </div>
        )}
      </div>

      {/* Query Input Box */}
      <form onSubmit={handleSend} className="pt-3 border-t border-[var(--border-subtle)] flex gap-2">
        <input
          type="text"
          value={queryText}
          onChange={(e) => setQueryText(e.target.value)}
          placeholder="Ask Copilot (e.g. 'What is our Paracetamol stock balance?' or 'Check cold chain alerts')..."
          className="flex-1 px-4 py-2.5 text-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-[var(--text-primary)] placeholder-[var(--text-secondary)] focus:outline-none focus:border-[var(--accent-teal)] font-mono"
        />
        <button
          type="submit"
          disabled={isLoading || !queryText.trim()}
          className="px-5 py-2.5 text-xs font-medium bg-[var(--accent-teal)] text-white hover:bg-[var(--accent-teal)]/90 transition-colors flex items-center gap-1.5 disabled:opacity-50 font-mono"
        >
          <Send className="w-3.5 h-3.5" /> Submit
        </button>
      </form>
    </div>
  );
};

/**
 * Copilot Feature Module
 * Natural-language conversational supply assistant with grounded RLS citations.
 */

export interface CopilotMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  citations?: Array<{ title: string; source: string; snippet: string }>;
}


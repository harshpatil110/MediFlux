/**
 * Types for Network Copilot conversational UI and structured reference citations (Task M8).
 */

export interface CopilotReference {
  id: string;
  type: 'inventory' | 'batch' | 'approval' | 'cascade' | 'node' | string;
  label: string;
  node_id?: string;
  node_name?: string;
  product_id?: string;
  barcode?: string;
  deep_link?: string;
  metadata?: Record<string, any>;
}

export interface CopilotChatMessage {
  id: string;
  sender: 'user' | 'copilot';
  text: string;
  timestamp: string;
  trace_id?: string;
  tools_used?: string[];
  activity_steps?: string[];
  references?: CopilotReference[];
  error?: {
    code?: string;
    message: string;
    retryable?: boolean;
  };
}

export interface SuggestedQuestion {
  text: string;
  category?: string;
}

export interface CopilotQueryApiPayload {
  question?: string;
  query?: string;
  stream?: boolean;
  region?: string;
  node_id?: string;
}

export interface CopilotQueryApiResponse {
  question: string;
  answer: string;
  references?: CopilotReference[];
  tools_used?: string[];
  activity_steps?: string[];
  trace_id: string;
  correlation_id?: string;
  scope?: Record<string, any>;
}

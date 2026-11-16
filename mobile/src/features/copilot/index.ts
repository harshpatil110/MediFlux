/**
 * Copilot Feature Module (Task M8).
 * Natural-language conversational supply assistant with grounded RLS citations.
 */

export * from './types';
export * from './copilotErrors';
export * from './suggestedQuestions';
export * from './ReferenceChipList';

// Backwards compatibility
export type { CopilotChatMessage as CopilotMessage } from './types';

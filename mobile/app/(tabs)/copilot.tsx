/**
 * RLS-Scoped Natural Language Supply Chain Copilot Screen (Task M8.1).
 * Features progressive reasoning, live tool indicators, reference chips, and friendly LLM error recovery.
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  SafeAreaView,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { apiClient } from '../../src/api/client';
import { useAuth } from '../../src/features/auth/AuthContext';
import { colors, spacing, typography, radii } from '../../src/theme/tokens';
import { Badge } from '../../src/components/Badge';
import {
  CopilotChatMessage,
  CopilotQueryApiResponse,
} from '../../src/features/copilot/types';
import { getSuggestedQuestionsForRole } from '../../src/features/copilot/suggestedQuestions';
import { formatCopilotError } from '../../src/features/copilot/copilotErrors';
import { ReferenceChipList } from '../../src/features/copilot/ReferenceChipList';

const INITIAL_GREETING: CopilotChatMessage = {
  id: 'init-greeting',
  sender: 'copilot',
  text: 'Greetings. I am your MediFlux Autonomous Supply Chain Copilot. Ask me about real-time inventory balances, stockout risks, demand cascades, pending approvals, cold-chain excursions, or regulatory Schedule H compliance.',
  timestamp: 'Just now',
};

const THINKING_STEPS = [
  'Searching inventory & stockout risk...',
  'Checking pending approvals & batches...',
  'Analyzing multi-tier demand cascades...',
  'Synthesizing grounded answer...',
];

export default function CopilotScreen() {
  const router = useRouter();
  const { user, status } = useAuth();
  const [messages, setMessages] = useState<CopilotChatMessage[]>([INITIAL_GREETING]);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [activeStepText, setActiveStepText] = useState(THINKING_STEPS[0]);
  const [lastFailedQuery, setLastFailedQuery] = useState<string | null>(null);

  const flatListRef = useRef<FlatList>(null);
  const stepTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Suggested questions based on authenticated user's role
  const suggestedQuestions = getSuggestedQuestionsForRole(user?.role);

  // Clear chat automatically when user logs out
  useEffect(() => {
    if (status === 'unauthenticated' || !user) {
      setMessages([INITIAL_GREETING]);
      setLastFailedQuery(null);
    }
  }, [status, user]);

  // Clean up timer on unmount
  useEffect(() => {
    return () => {
      if (stepTimerRef.current) clearInterval(stepTimerRef.current);
    };
  }, []);

  const handleClearChat = () => {
    setMessages([INITIAL_GREETING]);
    setLastFailedQuery(null);
  };

  const handleSend = async (queryText?: string) => {
    const textToSend = (queryText || input).trim();
    if (!textToSend || isSending) return;

    const userMsgId = `usr-${Date.now()}`;
    const userMsg: CopilotChatMessage = {
      id: userMsgId,
      sender: 'user',
      text: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!queryText) setInput('');
    setIsSending(true);
    setLastFailedQuery(null);

    // Start cycling live activity step indicators
    let stepIndex = 0;
    setActiveStepText(THINKING_STEPS[0]);
    stepTimerRef.current = setInterval(() => {
      stepIndex = (stepIndex + 1) % THINKING_STEPS.length;
      setActiveStepText(THINKING_STEPS[stepIndex]);
    }, 1100);

    try {
      const response = await apiClient.post<CopilotQueryApiResponse>('/api/v1/copilot/query', {
        question: textToSend,
        query: textToSend,
      });

      const replyText =
        response.answer ||
        (response as any).response ||
        (response as any).content ||
        'Query processed successfully.';

      const copilotMsg: CopilotChatMessage = {
        id: `copilot-${Date.now()}`,
        sender: 'copilot',
        text: replyText,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        trace_id: response.trace_id || response.correlation_id,
        tools_used: response.tools_used || [],
        activity_steps: response.activity_steps || [],
        references: response.references || [],
      };

      setMessages((prev) => [...prev, copilotMsg]);
    } catch (err: any) {
      const formatted = formatCopilotError(err);
      setLastFailedQuery(textToSend);

      const errorMsg: CopilotChatMessage = {
        id: `copilot-err-${Date.now()}`,
        sender: 'copilot',
        text: formatted.message,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        error: {
          code: formatted.code,
          message: formatted.message,
          retryable: formatted.retryable,
        },
      };

      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      if (stepTimerRef.current) {
        clearInterval(stepTimerRef.current);
        stepTimerRef.current = null;
      }
      setIsSending(false);
      setTimeout(() => {
        flatListRef.current?.scrollToEnd({ animated: true });
      }, 100);
    }
  };

  const handleRetry = () => {
    if (lastFailedQuery) {
      handleSend(lastFailedQuery);
    }
  };

  const renderMessageItem = ({ item }: { item: CopilotChatMessage }) => {
    const isUser = item.sender === 'user';

    return (
      <View
        style={[
          styles.messageRow,
          isUser ? styles.messageRowUser : styles.messageRowCopilot,
        ]}
      >
        <View
          style={[
            styles.bubble,
            isUser ? styles.bubbleUser : styles.bubbleCopilot,
            item.error ? styles.bubbleError : null,
          ]}
        >
          {/* Header row in bubble */}
          <View style={styles.bubbleHeader}>
            <View style={styles.roleBadgeGroup}>
              <Badge
                label={isUser ? 'OPERATOR' : 'COPILOT AI'}
                variant={isUser ? 'neutral' : item.error ? 'coral' : 'teal'}
              />
              {item.trace_id ? (
                <View style={styles.tracePill}>
                  <Ionicons name="git-commit-outline" size={10} color={colors.accent.primary} />
                  <Text style={styles.traceText} numberOfLines={1}>
                    {item.trace_id.slice(0, 12)}
                  </Text>
                </View>
              ) : null}
            </View>
            <Text style={[styles.bubbleTime, isUser && styles.bubbleTimeUser]}>
              {item.timestamp}
            </Text>
          </View>

          {/* Error Banner */}
          {item.error ? (
            <View style={styles.errorBanner}>
              <View style={styles.errorHeaderRow}>
                <Ionicons name="alert-circle" size={16} color={colors.status.danger} />
                <Text style={styles.errorTitle}>
                  {item.error.code === 'LLM_PROVIDER_BUSY'
                    ? 'AI Assistant Busy'
                    : item.error.code === 'COPILOT_FORBIDDEN_SCOPE'
                    ? 'Restricted by Node Policy'
                    : 'Query Interrupted'}
                </Text>
              </View>
              <Text style={styles.errorBody}>{item.error.message}</Text>
              {item.error.retryable && (
                <TouchableOpacity
                  style={styles.retryBtn}
                  onPress={handleRetry}
                  activeOpacity={0.8}
                >
                  <Ionicons name="refresh" size={12} color={colors.text.inverse} />
                  <Text style={styles.retryBtnText}>RETRY QUESTION</Text>
                </TouchableOpacity>
              )}
            </View>
          ) : (
            <Text style={[styles.bubbleText, isUser && styles.bubbleTextUser]}>
              {item.text}
            </Text>
          )}

          {/* Tools Used Badges */}
          {item.tools_used && item.tools_used.length > 0 && !item.error ? (
            <View style={styles.toolsUsedRow}>
              <Text style={styles.toolsUsedLabel}>TOOLS:</Text>
              {item.tools_used.map((t, idx) => (
                <View key={`tool-${idx}`} style={styles.toolPill}>
                  <Text style={styles.toolPillText}>{t}</Text>
                </View>
              ))}
            </View>
          ) : null}

          {/* Reference Chips */}
          {item.references && item.references.length > 0 && !item.error ? (
            <ReferenceChipList
              references={item.references}
              userRole={user?.role}
            />
          ) : null}
        </View>
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
      >
        {/* Top Header */}
        <View style={styles.topHeader}>
          <View style={styles.headerLeft}>
            <Text style={styles.headerKicker}>NATURAL-LANGUAGE REASONING</Text>
            <Text style={styles.headerTitle}>Supply Chain Copilot</Text>
            {user?.node_name ? (
              <Text style={styles.headerNodeText} numberOfLines={1}>
                Node: {user.node_name} ({user.role?.toUpperCase()})
              </Text>
            ) : null}
          </View>

          <View style={styles.headerRight}>
            <TouchableOpacity
              style={styles.cascadeHistoryBtn}
              onPress={() => router.push('/cascade' as any)}
              accessibilityLabel="View Cascade History"
            >
              <Ionicons name="time-outline" size={14} color={colors.accent.primary} />
              <Text style={styles.cascadeHistoryText}>HISTORY</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.clearChatBtn}
              onPress={handleClearChat}
              accessibilityLabel="Clear chat session"
            >
              <Ionicons name="trash-outline" size={14} color={colors.text.secondary} />
            </TouchableOpacity>
          </View>
        </View>

        {/* Messages Feed */}
        <FlatList
          ref={flatListRef}
          data={messages}
          keyExtractor={(item) => item.id}
          renderItem={renderMessageItem}
          contentContainerStyle={styles.messagesList}
          onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: true })}
          ListFooterComponent={
            isSending ? (
              <View style={styles.activityBubble}>
                <ActivityIndicator size="small" color={colors.accent.primary} />
                <Text style={styles.activityText}>{activeStepText}</Text>
              </View>
            ) : null
          }
        />

        {/* Role-Aware Suggested Questions */}
        {!isSending && messages.length <= 3 && (
          <View style={styles.suggestionsContainer}>
            <Text style={styles.suggestionsHeader}>SUGGESTED QUESTIONS</Text>
            <View style={styles.suggestionsWrapper}>
              {suggestedQuestions.map((q, idx) => (
                <TouchableOpacity
                  key={`sq-${idx}`}
                  style={styles.suggestionChip}
                  onPress={() => handleSend(q)}
                  activeOpacity={0.7}
                >
                  <Ionicons name="sparkles-outline" size={12} color={colors.accent.primary} />
                  <Text style={styles.suggestionText} numberOfLines={2}>
                    {q}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        )}

        {/* Input Bar */}
        <View style={styles.inputBar}>
          <TextInput
            style={styles.textInput}
            value={input}
            onChangeText={setInput}
            placeholder="Ask about inventory, stockout, batches..."
            placeholderTextColor={colors.text.muted}
            multiline
            maxLength={400}
            editable={!isSending}
            returnKeyType="send"
            onSubmitEditing={() => handleSend()}
          />
          <TouchableOpacity
            style={[
              styles.sendBtn,
              (!input.trim() || isSending) && styles.sendBtnDisabled,
            ]}
            onPress={() => handleSend()}
            disabled={!input.trim() || isSending}
            activeOpacity={0.8}
            accessibilityLabel="Send question"
          >
            {isSending ? (
              <ActivityIndicator size="small" color={colors.text.inverse} />
            ) : (
              <Ionicons name="arrow-up" size={18} color={colors.text.inverse} />
            )}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.canvas.primary,
  },
  container: {
    flex: 1,
    backgroundColor: colors.canvas.primary,
  },
  topHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.base,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border.default,
    backgroundColor: colors.canvas.primary,
  },
  headerLeft: {
    flex: 1,
  },
  headerKicker: {
    fontFamily: typography.fontFamily.mono,
    fontSize: typography.fontSize.micro,
    color: colors.text.muted,
    letterSpacing: typography.letterSpacing.widest,
    fontWeight: typography.fontWeight.bold,
  },
  headerTitle: {
    fontFamily: typography.fontFamily.sans,
    fontSize: typography.fontSize.h2,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.primary,
  },
  headerNodeText: {
    fontFamily: typography.fontFamily.mono,
    fontSize: typography.fontSize.micro,
    color: colors.accent.primary,
    marginTop: 2,
  },
  headerRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  cascadeHistoryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: radii.sm,
    backgroundColor: colors.canvas.surface,
    borderWidth: 1,
    borderColor: colors.accent.border,
  },
  cascadeHistoryText: {
    fontFamily: typography.fontFamily.mono,
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.accent.primary,
  },
  clearChatBtn: {
    padding: 6,
    borderRadius: radii.sm,
    backgroundColor: colors.canvas.surface,
    borderWidth: 1,
    borderColor: colors.border.default,
  },
  messagesList: {
    padding: spacing.base,
    gap: spacing.md,
  },
  messageRow: {
    flexDirection: 'row',
    marginVertical: 4,
  },
  messageRowUser: {
    justifyContent: 'flex-end',
  },
  messageRowCopilot: {
    justifyContent: 'flex-start',
  },
  bubble: {
    maxWidth: '85%',
    borderRadius: radii.md,
    padding: spacing.md,
    borderWidth: 1,
  },
  bubbleUser: {
    backgroundColor: colors.text.primary, // Ink Black #031211
    borderColor: colors.text.primary,
  },
  bubbleCopilot: {
    backgroundColor: colors.canvas.surface,
    borderColor: colors.border.default,
  },
  bubbleError: {
    borderColor: colors.status.danger,
    backgroundColor: '#FEF2F2',
  },
  bubbleHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
    gap: spacing.sm,
  },
  roleBadgeGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  tracePill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
    backgroundColor: colors.canvas.elevated,
    paddingHorizontal: 4,
    paddingVertical: 1,
    borderRadius: radii.xs,
  },
  traceText: {
    fontFamily: typography.fontFamily.mono,
    fontSize: typography.fontSize.micro,
    color: colors.text.secondary,
  },
  bubbleTime: {
    fontFamily: typography.fontFamily.mono,
    fontSize: typography.fontSize.micro,
    color: colors.text.muted,
  },
  bubbleTimeUser: {
    color: '#9E988A',
  },
  bubbleText: {
    fontFamily: typography.fontFamily.sans,
    fontSize: typography.fontSize.body,
    color: colors.text.primary,
    lineHeight: 20,
  },
  bubbleTextUser: {
    color: colors.canvas.primary, // Warm Ivory text inside Ink Black bubble
  },
  toolsUsedRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: spacing.xs,
    flexWrap: 'wrap',
  },
  toolsUsedLabel: {
    fontFamily: typography.fontFamily.mono,
    fontSize: typography.fontSize.micro,
    color: colors.text.muted,
    fontWeight: typography.fontWeight.bold,
  },
  toolPill: {
    backgroundColor: colors.canvas.elevated,
    paddingHorizontal: 4,
    paddingVertical: 1,
    borderRadius: radii.xs,
    borderWidth: 1,
    borderColor: colors.border.subtle,
  },
  toolPillText: {
    fontFamily: typography.fontFamily.mono,
    fontSize: typography.fontSize.micro,
    color: colors.text.secondary,
  },
  errorBanner: {
    gap: 6,
  },
  errorHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  errorTitle: {
    fontFamily: typography.fontFamily.sans,
    fontSize: typography.fontSize.caption,
    fontWeight: typography.fontWeight.bold,
    color: colors.status.danger,
  },
  errorBody: {
    fontFamily: typography.fontFamily.sans,
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    lineHeight: 18,
  },
  retryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.status.danger,
    paddingVertical: 5,
    paddingHorizontal: 10,
    borderRadius: radii.xs,
    alignSelf: 'flex-start',
    marginTop: 4,
  },
  retryBtnText: {
    fontFamily: typography.fontFamily.mono,
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.inverse,
  },
  activityBubble: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: colors.canvas.surface,
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.md,
    paddingVertical: 10,
    paddingHorizontal: 14,
    alignSelf: 'flex-start',
    marginTop: 4,
  },
  activityText: {
    fontFamily: typography.fontFamily.sans,
    fontSize: typography.fontSize.caption,
    color: colors.text.secondary,
    fontStyle: 'italic',
  },
  suggestionsContainer: {
    paddingHorizontal: spacing.base,
    paddingBottom: spacing.xs,
  },
  suggestionsHeader: {
    fontFamily: typography.fontFamily.mono,
    fontSize: typography.fontSize.micro,
    fontWeight: typography.fontWeight.bold,
    color: colors.text.muted,
    letterSpacing: typography.letterSpacing.wide,
    marginBottom: spacing.xs,
  },
  suggestionsWrapper: {
    gap: 6,
  },
  suggestionChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.canvas.surface,
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.sm,
    paddingVertical: 6,
    paddingHorizontal: 10,
  },
  suggestionText: {
    flex: 1,
    fontFamily: typography.fontFamily.sans,
    fontSize: typography.fontSize.caption,
    color: colors.text.primary,
  },
  inputBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.sm,
    backgroundColor: colors.canvas.surface,
    borderTopWidth: 1,
    borderTopColor: colors.border.default,
  },
  textInput: {
    flex: 1,
    backgroundColor: colors.canvas.elevated,
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 8,
    fontSize: typography.fontSize.body,
    fontFamily: typography.fontFamily.sans,
    color: colors.text.primary,
    maxHeight: 90,
  },
  sendBtn: {
    backgroundColor: colors.accent.primary,
    width: 38,
    height: 38,
    borderRadius: radii.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendBtnDisabled: {
    backgroundColor: colors.border.default,
    opacity: 0.6,
  },
});

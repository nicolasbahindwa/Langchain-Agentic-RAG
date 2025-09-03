import React, { createContext, useContext, useState, useEffect, useMemo, useRef, ReactNode } from 'react';
import { useSearchParam } from '../hooks/useSearchParam';
import { useStream } from "@langchain/langgraph-sdk/react";
import type { Message as LangGraphMessage } from "@langchain/langgraph-sdk";

// ═══════════════════════════════════════════════════════════════════════════════
// ─── TYPE DEFINITIONS ──────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════════

export interface ChatMessage {
  id: string;
  content: string;
  type: 'human' | 'ai';
  timestamp?: Date;
  isInterrupted?: boolean;
  needsHumanFeedback?: boolean;
  versions?: string[]; // Multiple generations
  currentVersionIndex?: number;
  isIncomplete?: boolean;
  originalHumanMessageId?: string; // Link AI responses to their triggering human message
  isGeneratingVersion?: boolean; // Flag when generating a new version
}

export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, any>;
}

export interface ToolActivity {
  toolCalls: ToolCall[];
}

interface StreamValues {
  messages?: LangGraphMessage[];
  is_generating?: boolean;
  needs_clarification?: boolean;
}

export interface ChatContextType {
  // State
  messages: ChatMessage[];
  threadId: string | null;
  isGenerating: boolean;
  isPreparingResponse: boolean;
  toolActivity: ToolActivity | null;
  hasActiveToolCalls: boolean;
  needsHumanFeedback: boolean;
  
  // UI States
  showPreparingIndicator: boolean;
  showToolActivity: boolean;
  showGeneratingIndicator: boolean;
  
  // Actions
  handleSubmit: (input: string) => void;
  handleStop: () => void;
  handleNewThread: () => void;
  handleRegenerate: (messageId: string) => void;
  handleEditMessage: (messageId: string, newContent: string) => void;
  handleResume: (messageId: string) => void;
  handleVersionChange: (messageId: string, versionIndex: number) => void;
  handleHumanFeedback: (feedback: string) => void;
  
  // Status
  getStatusText: () => string;
  getStatusColor: () => string;
}

// ═══════════════════════════════════════════════════════════════════════════════
// ─── UTILITY FUNCTIONS ─────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════════

// Helper function to find last index (compatible alternative to findLastIndex)
function findLastIndex<T>(array: T[], predicate: (item: T, index: number) => boolean): number {
  for (let i = array.length - 1; i >= 0; i--) {
    if (predicate(array[i], i)) {
      return i;
    }
  }
  return -1;
}

// Helper function to get the last human message ID
function getLastHumanMessageId(messages: LangGraphMessage[]): string | undefined {
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].type === 'human') {
      return messages[i].id;
    }
  }
  return undefined;
}

// ═══════════════════════════════════════════════════════════════════════════════
// ─── DATA PROCESSING ────────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════════

const processStreamMessages = (rawMessages: LangGraphMessage[] | undefined, streamValues: StreamValues | undefined) => {
  if (!rawMessages) {
    return { 
      userMessages: [], 
      toolActivity: null, 
      hasActiveToolCalls: false,
      needsHumanFeedback: false
    };
  }

  const userMessages: ChatMessage[] = [];
  let activeToolCalls: ToolCall[] = [];
  let hasActiveToolCalls = false;
  let needsHumanFeedback = false;

  // Check if agent needs clarification (human-in-the-loop)
  if (streamValues?.needs_clarification) {
    needsHumanFeedback = true;
  }

  // Process each message in the stream
  for (let i = 0; i < rawMessages.length; i++) {
    const msg = rawMessages[i];
    
    if (msg.type === 'human') {
      const content = typeof msg.content === 'string' ? msg.content : '';
      
      if (content.trim()) {
        userMessages.push({ 
          id: msg.id || `human-${i}`, 
          type: 'human', 
          content,
          timestamp: new Date()
        });
      }

      // Reset tool activity when new human message arrives
      activeToolCalls = [];
      hasActiveToolCalls = false;
    } 
    else if (msg.type === 'ai') {
      // Check for tool calls in AI messages
      const toolCalls = (msg as any).tool_calls;
      
      if (toolCalls && Array.isArray(toolCalls) && toolCalls.length > 0) {
        // AI message with tool calls - store them for display
        activeToolCalls = toolCalls.map((call: any) => ({
          id: call.id || `tool-${i}`,
          name: call.name || 'unknown_tool',
          args: call.args || {}
        }));
        hasActiveToolCalls = true;
      } 
      else if (msg.content && typeof msg.content === 'string' && msg.content.trim()) {
        // AI message with actual content - this is the response
        userMessages.push({ 
          id: msg.id || `ai-${i}`, 
          type: 'ai', 
          content: msg.content,
          timestamp: new Date(),
          needsHumanFeedback: needsHumanFeedback,
          versions: [msg.content],
          currentVersionIndex: 0
        });

        // Clear tool activity once we have the final response
        activeToolCalls = [];
        hasActiveToolCalls = false;
      }
    }
    else if (msg.type === 'tool') {
      // Tool execution messages - keep tool activity visible
      hasActiveToolCalls = activeToolCalls.length > 0;
    }
  }

  const toolActivity: ToolActivity | null = hasActiveToolCalls ? 
    { toolCalls: activeToolCalls } : null;

  return { userMessages, toolActivity, hasActiveToolCalls, needsHumanFeedback };
};

// ═══════════════════════════════════════════════════════════════════════════════
// ─── CONTEXT DEFINITION ────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════════

const ChatContext = createContext<ChatContextType | undefined>(undefined);

export const useChatContext = () => {
  const context = useContext(ChatContext);
  if (context === undefined) {
    throw new Error('useChatContext must be used within a ChatProvider');
  }
  return context;
};

// ═══════════════════════════════════════════════════════════════════════════════
// ─── CHAT PROVIDER ─────────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════════

interface ChatProviderProps {
  children: ReactNode;
  apiUrl?: string;
  assistantId?: string;
}

export const ChatProvider: React.FC<ChatProviderProps> = ({ 
  children, 
  apiUrl = 'http://localhost:2024',
  assistantId = 'orchestrator'
}) => {
  const [threadId, setThreadId] = useSearchParam('threadId');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isPreparingResponse, setIsPreparingResponse] = useState(false);

  // Stream connection with proper typing
  const stream = useStream<StreamValues>({
    apiUrl,
    assistantId,
    threadId: threadId || undefined,
    onThreadId: setThreadId,
    reconnectOnMount: true,
    onMessages: (messages) => {
      // Handle regeneration messages
      const lastMessage = messages[messages.length - 1];
      if (lastMessage?.type === 'ai') {
        const existingAIMessage = messages.find(msg => 
          msg.type === 'ai' && 
          msg.originalHumanMessageId === getLastHumanMessageId(messages)
        );
        
        if (existingAIMessage) {
          // This is a regeneration, update existing message
          setMessages(prev => prev.map(msg => {
            if (msg.id === existingAIMessage.id) {
              const versions = msg.versions || [msg.content];
              return {
                ...msg,
                versions: [...versions, lastMessage.content],
                currentVersionIndex: versions.length,
                content: lastMessage.content,
                isGeneratingVersion: false,
                isIncomplete: false
              };
            }
            return msg;
          }));
        }
      }
    }
  });

  // Process messages for display
  const { userMessages, toolActivity, hasActiveToolCalls, needsHumanFeedback } = useMemo(
    () => processStreamMessages(stream.messages, stream.values),
    [stream.messages, stream.values]
  );

  // Update messages with proper regeneration handling
  useEffect(() => {
    if (isPreparingResponse && (hasActiveToolCalls || userMessages.some(msg => msg.type === 'ai'))) {
      setIsPreparingResponse(false);
    }

    setMessages(userMessages);
  }, [userMessages, hasActiveToolCalls, isPreparingResponse]);

  // UI state logic
  const isGenerating = stream.values?.is_generating || stream.isLoading || false;
  const showPreparingIndicator = isPreparingResponse;
  const showToolActivity = hasActiveToolCalls && messages.length > 0 && !isPreparingResponse;
  const showGeneratingIndicator = isGenerating && !showToolActivity && messages.length > 0 && !isPreparingResponse;

  const getStatusText = (): string => {
    if (showPreparingIndicator) return 'Preparing';
    if (needsHumanFeedback) return 'Waiting for feedback';
    if (showToolActivity) return 'Researching';
    if (showGeneratingIndicator) return 'Generating';
    if (stream.isLoading) return 'Processing';
    return 'Ready';
  };

  const getStatusColor = (): string => {
    if (showPreparingIndicator) return 'bg-blue-500 animate-pulse';
    if (needsHumanFeedback) return 'bg-amber-500 animate-pulse';
    if (showToolActivity || showGeneratingIndicator || stream.isLoading) {
      return 'bg-green-500 animate-pulse';
    }
    return 'bg-gray-400';
  };

  // Event handlers
  const handleSubmit = (input: string) => {
    setIsPreparingResponse(true);
    stream.submit({ 
      messages: [{ type: "human", content: input }],
      streamResumable: true
    });
  };

  const handleStop = () => {
    stream.stop();
    
    // Mark the last AI message as incomplete if it exists
    setMessages(prev => {
      const lastAIIndex = findLastIndex(prev, msg => msg.type === 'ai');
      if (lastAIIndex >= 0) {
        const updated = [...prev];
        updated[lastAIIndex] = {
          ...updated[lastAIIndex],
          isIncomplete: true,
          versions: updated[lastAIIndex].versions || [updated[lastAIIndex].content],
          currentVersionIndex: updated[lastAIIndex].currentVersionIndex || 0
        };
        return updated;
      }
      return prev;
    });
  };

  const handleNewThread = () => {
    setThreadId(null);
    setMessages([]);
  };

  const handleRegenerate = (messageId: string) => {
    const messageIndex = messages.findIndex(msg => msg.id === messageId);
    if (messageIndex === -1) return;

    const aiMessage = messages[messageIndex];
    if (aiMessage.type !== 'ai') return;

    // Find the corresponding human message
    const correspondingHumanMessage = [...messages.slice(0, messageIndex)]
      .reverse().find(msg => msg.type === 'human');
    
    if (!correspondingHumanMessage) return;

    // Mark as generating new version
    setMessages(prev => prev.map(msg => 
      msg.id === messageId 
        ? { ...msg, isGeneratingVersion: true }
        : msg
    ));

    // Use the same thread for regeneration (don't create new thread)
    const regenerateInSameThread = async () => {
      try {
        // Use the existing thread but with a new run
        const response = await fetch(`${apiUrl}/threads/${threadId}/runs/stream`, {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream'
          },
          body: JSON.stringify({
            assistant_id: assistantId,
            input: {
              messages: [{ type: "human", content: correspondingHumanMessage.content }],
              regenerate: true, // Add flag to indicate regeneration
              streamResumable: true
            }
          })
        });

        if (!response.body) throw new Error('No response body');

        const reader = response.body.getReader();
        let newContent = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = new TextDecoder().decode(value);
          const lines = chunk.split('\n').filter(line => line.trim());
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.event === 'messages/partial') {
                  const content = data.data?.content;
                  if (content && typeof content === 'string') {
                    newContent = content;
                  }
                }
              } catch (e) {
                // Ignore parsing errors
              }
            }
          }
        }

        // Add new version to existing message
        if (newContent) {
          setMessages(prev => prev.map(msg => {
            if (msg.id === messageId) {
              const versions = msg.versions || [msg.content];
              return {
                ...msg,
                versions: [...versions, newContent],
                currentVersionIndex: versions.length,
                content: newContent,
                isGeneratingVersion: false,
                isIncomplete: false // Mark as complete
              };
            }
            return msg;
          }));
        }
      } catch (error) {
        console.error('Regeneration failed:', error);
        // Clear generating state
        setMessages(prev => prev.map(msg => 
          msg.id === messageId 
            ? { ...msg, isGeneratingVersion: false }
            : msg
        ));
      }
    };

    regenerateInSameThread();
  };

  const handleEditMessage = (messageId: string, newContent: string) => {
    const messageIndex = messages.findIndex(msg => msg.id === messageId);
    if (messageIndex === -1) return;

    const message = messages[messageIndex];
    if (message.type !== 'human') return;

    // Update the message content
    const updatedMessages = [...messages];
    updatedMessages[messageIndex] = {
      ...message,
      content: newContent
    };

    // Remove all messages after this edited message
    const messagesToKeep = updatedMessages.slice(0, messageIndex + 1);
    setMessages(messagesToKeep);

    // Resend the edited message
    stream.submit({ 
      messages: [{ type: "human", content: newContent }],
      streamResumable: true
    });
  };

  const handleResume = (messageId: string) => {
    // Find the specific message to resume
    const message = messages.find(msg => msg.id === messageId);
    if (!message || !message.isIncomplete) return;

    // Mark as resuming
    setMessages(prev => prev.map(msg => 
      msg.id === messageId 
        ? { ...msg, isGeneratingVersion: true, isIncomplete: false }
        : msg
    ));

    // Resume the stream for this specific message
    stream.resume({
      messages: [{ type: "human", content: messages.find(msg => msg.type === 'human' && msg.id === message.originalHumanMessageId)?.content || '' }],
      continueFrom: messageId // Pass the message ID to continue from
    });
  };

  const handleVersionChange = (messageId: string, versionIndex: number) => {
    setMessages(prev => 
      prev.map(msg => 
        msg.id === messageId 
          ? { ...msg, currentVersionIndex: versionIndex }
          : msg
      )
    );
  };

  const handleHumanFeedback = (feedback: string) => {
    stream.submit({ 
      messages: [{ type: "human", content: feedback }],
      streamResumable: true
    });
  };

  const contextValue: ChatContextType = {
    // State
    messages,
    threadId,
    isGenerating,
    isPreparingResponse,
    toolActivity,
    hasActiveToolCalls,
    needsHumanFeedback,
    
    // UI States
    showPreparingIndicator,
    showToolActivity,
    showGeneratingIndicator,
    
    // Actions
    handleSubmit,
    handleStop,
    handleNewThread,
    handleRegenerate,
    handleEditMessage,
    handleResume,
    handleVersionChange,
    handleHumanFeedback,
    
    // Status
    getStatusText,
    getStatusColor,
  };

  return (
    <ChatContext.Provider value={contextValue}>
      {children}
    </ChatContext.Provider>
  );
};
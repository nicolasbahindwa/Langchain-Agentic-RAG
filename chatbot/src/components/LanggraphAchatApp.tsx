import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import {EnhancedContentRenderer}  from './renders/EnhancedContentRenderer';
import { useStream } from "@langchain/langgraph-sdk/react";
import type { Message as LangGraphMessage } from "@langchain/langgraph-sdk";
import { 
  Bot, 
  Send, 
  Square, 
  RefreshCw, 
  Edit3, 
  Loader, 
  Globe, 
  Search, 
  CheckCircle, 
  User, 
  Copy, 
  Check, 
  ChevronLeft, 
  ChevronRight, 
  Plus, 
  MessageSquare, 
  Settings,
  Brain,
  Zap,
  Play,
  Pause,
  AlertCircle,
  RotateCcw
} from 'lucide-react';

// ═══════════════════════════════════════════════════════════════════════════════
// ─── CUSTOM HOOKS ──────────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════════

function useSearchParam(key: string): [string | null, (value: string | null) => void] {
  const [value, setValue] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    const params = new URLSearchParams(window.location.search);
    return params.get(key) ?? null;
  });

  const update = useCallback((newValue: string | null) => {
    setValue(newValue);
    if (typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    if (newValue == null) url.searchParams.delete(key);
    else url.searchParams.set(key, newValue);
    window.history.pushState({}, '', url.toString());
  }, [key]);

  return [value, update];
}

// ═══════════════════════════════════════════════════════════════════════════════
// ─── TYPE DEFINITIONS ──────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════════

interface ChatMessage {
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

interface ToolCall {
  id: string;
  name: string;
  args: Record<string, any>;
}

interface ToolActivity {
  toolCalls: ToolCall[];
}

interface StreamValues {
  messages?: LangGraphMessage[];
  is_generating?: boolean;
  needs_clarification?: boolean;
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
// ─── UI COMPONENTS ──────────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════════

const PreparingIndicator: React.FC = () => (
  <div className="flex justify-start mb-6">
    <div className="max-w-4xl flex gap-3 items-start">
      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center flex-shrink-0 shadow-lg">
        <Bot className="w-5 h-5 text-white" />
      </div>
      <div className="bg-gradient-to-br from-gray-50 to-blue-50 border border-gray-200 rounded-2xl px-4 py-3 shadow-sm flex items-center gap-3">
        <Loader className="w-4 h-4 animate-spin text-blue-600" />
        <span className="text-sm font-medium text-gray-600">Preparing response...</span>
      </div>
    </div>
  </div>
);

const GeneratingIndicator: React.FC = () => (
  <div className="flex justify-start mb-6">
    <div className="max-w-4xl flex gap-3 items-start">
      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center flex-shrink-0 shadow-lg">
        <Bot className="w-5 h-5 text-white" />
      </div>
      <div className="bg-white border border-gray-200 rounded-2xl px-4 py-3 shadow-sm flex items-center gap-3">
        <div className="flex space-x-1">
          <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
          <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
          <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
        </div>
        <span className="text-sm font-medium text-gray-600">Thinking...</span>
      </div>
    </div>
  </div>
);

const HumanFeedbackPrompt: React.FC<{
  message: ChatMessage;
  onFeedback: (feedback: string) => void;
}> = ({ message, onFeedback }) => {
  const [feedback, setFeedback] = useState('');

  const handleSubmit = () => {
    if (feedback.trim()) {
      onFeedback(feedback.trim());
      setFeedback('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 mt-3">
      <div className="flex items-center gap-2 mb-3">
        <AlertCircle className="w-4 h-4 text-amber-600" />
        <span className="text-sm font-semibold text-amber-800">
          Human Feedback Needed
        </span>
      </div>
      <p className="text-sm text-amber-700 mb-3">
        The AI needs more information to provide a better answer. Please provide additional details or clarification.
      </p>
      <div className="flex gap-2">
        <textarea
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Provide more details or clarify your question..."
          className="flex-1 border border-amber-300 rounded-lg px-3 py-2 text-sm resize-none min-h-[60px] focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
          rows={2}
        />
        <button
          onClick={handleSubmit}
          disabled={!feedback.trim()}
          className="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:bg-amber-300 disabled:cursor-not-allowed text-sm font-medium flex items-center gap-2"
        >
          <Send className="w-4 h-4" />
          Send
        </button>
      </div>
    </div>
  );
};

const ToolActivityIndicator: React.FC<{ activity: ToolActivity }> = ({ activity }) => {
  const getToolIcon = (toolName: string) => {
    if (toolName.includes('search') || toolName.includes('web')) {
      return <Search className="w-4 h-4 text-blue-500" />;
    }
    if (toolName.includes('brain') || toolName.includes('analyze')) {
      return <Brain className="w-4 h-4 text-purple-500" />;
    }
    return <Settings className="w-4 h-4 text-gray-500" />;
  };
  
  const getToolDisplayName = (toolName: string): string => {
    return toolName
      .replace(/_/g, ' ')
      .replace(/search/gi, 'Search')
      .replace(/web/gi, 'Web')
      .replace(/\b\w/g, l => l.toUpperCase());
  };
  
  return (
    <div className="flex justify-start mb-6">
      <div className="max-w-4xl flex gap-3 items-start">
        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center flex-shrink-0 shadow-lg">
          <Bot className="w-5 h-5 text-white" />
        </div>
        <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-100 rounded-2xl p-4 shadow-sm">
          <div className="flex items-center gap-2 mb-3">
            <Zap className="w-4 h-4 text-blue-600" />
            <span className="text-sm font-semibold text-blue-800">Research in Progress</span>
            <Loader className="w-4 h-4 animate-spin text-blue-600" />
          </div>
          <div className="space-y-2">
            {activity.toolCalls.map((call, index) => (
              <div key={call.id} className="flex items-center gap-3 text-sm">
                {getToolIcon(call.name)}
                <span className="font-medium text-gray-700">
                  {getToolDisplayName(call.name)}
                </span>
                <span className="text-gray-500">•</span>
                <span className="text-gray-600 truncate flex-1">
                  {call.args.query || call.args.input || 'Processing...'}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// ─── MESSAGE CAROUSEL COMPONENT ────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════════

const MessageCarousel: React.FC<{
  versions: string[];
  currentIndex: number;
  onVersionChange: (index: number) => void;
  onRegenerate?: () => void;
  isGenerating?: boolean;
  isIncomplete?: boolean;
  onResume?: () => void;
}> = ({ versions, currentIndex, onVersionChange, onRegenerate, isGenerating, isIncomplete, onResume }) => {
  // Calculate proper version display
  const completedVersions = versions.length;
  const totalVersionsIncludingGenerating = isGenerating ? completedVersions + 1 : completedVersions;
  const displayCurrentIndex = currentIndex + 1;
  const displayTotalVersions = Math.max(1, totalVersionsIncludingGenerating);
  
  const hasMultipleVersions = completedVersions > 1 || isGenerating;

  return (
    <div className="mt-4 pt-3 border-t border-gray-100">
      <div className="flex items-center justify-between">
        {/* Left side - Version info and navigation */}
        <div className="flex items-center gap-3">
          {isGenerating ? (
            <div className="flex items-center gap-2">
              <Loader className="w-4 h-4 animate-spin text-blue-600" />
              <span className="text-sm text-blue-600 font-medium">
                {completedVersions === 0 ? 'Generating...' : `Generating version ${completedVersions + 1}...`}
              </span>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <RotateCcw className="w-3 h-3 text-gray-500" />
              <span className="text-xs font-medium text-gray-600">
                {completedVersions} {completedVersions === 1 ? 'version' : 'versions'}
              </span>
            </div>
          )}

          {/* Carousel Navigation */}
          {hasMultipleVersions && !isGenerating && (
            <div className="flex items-center gap-1 ml-2">
              <button
                onClick={() => onVersionChange(Math.max(0, currentIndex - 1))}
                disabled={currentIndex === 0}
                className="p-1 rounded-md hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                title="Previous version"
              >
                <ChevronLeft className="w-4 h-4 text-gray-600" />
              </button>
              
              <div className="px-3 py-1 bg-gray-100 rounded-full text-xs font-medium text-gray-700 min-w-[65px] text-center">
                {displayCurrentIndex}/{displayTotalVersions}
              </div>
              
              <button
                onClick={() => onVersionChange(Math.min(completedVersions - 1, currentIndex + 1))}
                disabled={currentIndex === completedVersions - 1}
                className="p-1 rounded-md hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                title="Next version"
              >
                <ChevronRight className="w-4 h-4 text-gray-600" />
              </button>
            </div>
          )}

          {/* Show version counter even when generating */}
          {isGenerating && completedVersions > 0 && (
            <div className="px-3 py-1 bg-blue-100 rounded-full text-xs font-medium text-blue-700 min-w-[80px] text-center ml-2">
              {displayCurrentIndex}/{displayTotalVersions}
            </div>
          )}
        </div>

        {/* Right side - Action buttons */}
        <div className="flex items-center gap-2">
          {/* Resume button for incomplete versions */}
          {isIncomplete && onResume && !isGenerating && (
            <button
              onClick={onResume}
              className="text-xs px-2 py-1 bg-green-100 hover:bg-green-200 text-green-700 rounded transition-colors flex items-center gap-1"
              title="Resume this version"
            >
              <Play className="w-3 h-3" />
              Resume
            </button>
          )}

          {/* Regenerate button */}
          {onRegenerate && !isGenerating && (
            <button
              onClick={onRegenerate}
              className="text-xs px-2 py-1 bg-blue-100 hover:bg-blue-200 text-blue-700 rounded transition-colors flex items-center gap-1"
              title="Generate new version"
            >
              <RotateCcw className="w-3 h-3" />
              Regenerate
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// ─── MESSAGE BUBBLE COMPONENT ──────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════════

const MessageBubble: React.FC<{ 
  message: ChatMessage; 
  isLastMessage?: boolean;
  onRegenerate?: () => void;
  onResume?: () => void;
  onHumanFeedback?: (feedback: string) => void;
  onEditMessage?: (messageId: string, newContent: string) => void;
  onVersionChange?: (index: number) => void;
  userQuery?: string; 
}> = ({ message, isLastMessage = false, onRegenerate, onResume, onHumanFeedback, onEditMessage, onVersionChange ,  userQuery = ''}) => {
  const [copied, setCopied] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(message.content);

  const handleCopy = async () => {
    try {
      const versions = message.versions || [message.content];
      const currentIndex = message.currentVersionIndex || 0;
      const currentContent = versions[currentIndex] || message.content;
      await navigator.clipboard.writeText(currentContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy text:', err);
    }
  };

  const handleStartEdit = () => {
    setIsEditing(true);
    setEditContent(message.content);
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditContent(message.content);
  };

  const handleSaveEdit = () => {
    if (editContent.trim() && editContent.trim() !== message.content) {
      onEditMessage?.(message.id, editContent.trim());
    }
    setIsEditing(false);
  };

  const handleEditKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSaveEdit();
    } else if (e.key === 'Escape') {
      handleCancelEdit();
    }
  };

  const versions = message.versions || [message.content];
  const currentIndex = message.currentVersionIndex || 0;
  const currentContent = versions[currentIndex] || message.content;

  return (
    <div className={`flex ${message.type === 'human' ? 'justify-end' : 'justify-start'} mb-6 group`}>
      <div className={`max-w-4xl flex gap-3 ${message.type === 'human' ? 'flex-row-reverse' : 'flex-row'} items-start`}>
        {/* Avatar */}
        <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 shadow-lg ${
          message.type === 'human' 
            ? 'bg-gradient-to-br from-gray-600 to-gray-800' 
            : 'bg-gradient-to-br from-blue-500 to-purple-600'
        }`}>
          {message.type === 'human' ? (
            <User className="w-5 h-5 text-white" />
          ) : (
            <Bot className="w-5 h-5 text-white" />
          )}
        </div>

        {/* Message Content */}
        <div className="flex-1 min-w-0">
          <div className={`rounded-2xl px-4 py-3 shadow-sm relative group ${
            message.type === 'human' 
              ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white ml-12' 
              : 'bg-white border border-gray-200'
          }`}>
            {/* Message Content */}
            {isEditing && message.type === 'human' ? (
              // Edit Mode for Human Messages
              <div className="space-y-3">
                <textarea
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  onKeyDown={handleEditKeyDown}
                  className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2 text-white placeholder-white/70 resize-none min-h-[60px] focus:outline-none focus:border-white/40"
                  placeholder="Edit your message..."
                  autoFocus
                />
                <div className="flex justify-end gap-2">
                  <button
                    onClick={handleCancelEdit}
                    className="px-3 py-1.5 bg-white/20 hover:bg-white/30 rounded-lg text-xs text-white transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSaveEdit}
                    disabled={!editContent.trim() || editContent.trim() === message.content}
                    className="px-3 py-1.5 bg-white text-blue-600 hover:bg-white/90 rounded-lg text-xs font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Save & Resend
                  </button>
                </div>
              </div>
            ) : (
              // Normal Display Mode
              <>
                {message.type === 'ai' ? (
                  <EnhancedContentRenderer 
                    content={currentContent} 
                    userQuery={userQuery} // Pass the user query for context
                  />
                ) : (
                  <p className="whitespace-pre-wrap text-sm leading-relaxed">
                    {currentContent}
                  </p>
                )}

                {/* Carousel for AI messages */}
                {message.type === 'ai' && (
                  <MessageCarousel
                    versions={versions}
                    currentIndex={currentIndex}
                    onVersionChange={onVersionChange || (() => {})}
                    onRegenerate={onRegenerate}
                    isGenerating={message.isGeneratingVersion}
                    isIncomplete={message.isIncomplete}
                    onResume={onResume}
                  />
                )}
              </>
            )}

            {/* Action Buttons */}
            {!isEditing && (
              <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                {/* AI Message Actions */}
                {message.type === 'ai' && (
                  <button
                    onClick={handleCopy}
                    className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600"
                    title="Copy current version"
                  >
                    {copied ? (
                      <Check className="w-4 h-4 text-green-500" />
                    ) : (
                      <Copy className="w-4 h-4" />
                    )}
                  </button>
                )}

                {/* Human Message Actions */}
                {message.type === 'human' && onEditMessage && (
                  <button
                    onClick={handleStartEdit}
                    className="p-1.5 rounded-lg hover:bg-white/20 text-white/70 hover:text-white"
                    title="Edit message"
                  >
                    <Edit3 className="w-4 h-4" />
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Human Feedback Prompt */}
          {message.type === 'ai' && message.needsHumanFeedback && onHumanFeedback && (
            <HumanFeedbackPrompt
              message={message}
              onFeedback={onHumanFeedback}
            />
          )}

          {/* Timestamp */}
          {message.timestamp && (
            <div className={`text-xs text-gray-400 mt-1 ${
              message.type === 'human' ? 'text-right mr-12' : 'text-left'
            }`}>
              {message.timestamp.toLocaleTimeString([], { 
                hour: '2-digit', 
                minute: '2-digit' 
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const ChatInput: React.FC<{
  onSubmit: (message: string) => void;
  isLoading: boolean;
  onStop: () => void;
}> = ({ onSubmit, isLoading, onStop }) => {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = () => {
    if (!input.trim() || isLoading) return;
    onSubmit(input.trim());
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`;
    }
  }, [input]);

  return (
    <div className="border-t bg-white sticky bottom-0 z-10">
      <div className="max-w-5xl mx-auto p-4">
        <div className="flex gap-3 items-end">
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask me anything about research, analysis, or any topic..."
              className="w-full border-2 border-gray-200 rounded-2xl px-4 py-3 resize-none min-h-[48px] max-h-[120px] focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all duration-200 text-gray-800 placeholder-gray-500"
              rows={1}
              disabled={isLoading}
            />
          </div>

          {isLoading ? (
            <button
              type="button"
              onClick={onStop}
              className="p-3 bg-red-500 text-white rounded-2xl hover:bg-red-600 transition-all duration-200 flex items-center justify-center shadow-lg hover:shadow-xl transform hover:scale-105"
              title="Stop generation"
            >
              <Square className="w-5 h-5" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!input.trim()}
              className="p-3 bg-gradient-to-br from-blue-500 to-purple-600 text-white rounded-2xl hover:from-blue-600 hover:to-purple-700 disabled:from-gray-300 disabled:to-gray-400 disabled:cursor-not-allowed transition-all duration-200 flex items-center justify-center shadow-lg hover:shadow-xl transform hover:scale-105 disabled:transform-none disabled:shadow-lg"
              title="Send message"
            >
              <Send className="w-5 h-5" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

const Sidebar: React.FC<{
  onNewThread: () => void;
}> = ({ onNewThread }) => (
  <div className="w-72 bg-gradient-to-b from-gray-900 via-gray-800 to-gray-900 text-white flex flex-col h-full shadow-2xl">
    {/* Header */}
    <div className="p-6 border-b border-gray-700">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-lg">
          <Brain className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="font-bold text-lg text-white">Research AI</h1>
          <p className="text-xs text-gray-400">Powered by LangGraph</p>
        </div>
      </div>

      <button
        onClick={onNewThread}
        className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white py-3 px-4 rounded-xl font-medium flex items-center gap-2 transition-all duration-200 shadow-lg hover:shadow-xl transform hover:scale-105"
      >
        <Plus className="w-4 h-4" />
        New Research Session
      </button>
    </div>

    {/* Content Area */}
    <div className="flex-1 p-6">
      <div className="space-y-4">
        <div className="text-xs text-gray-400 uppercase tracking-wide font-semibold">
          Features
        </div>
        <div className="space-y-3">
          <div className="flex items-center gap-3 text-sm text-gray-300">
            <Search className="w-4 h-4 text-blue-400" />
            Web Search & Analysis
          </div>
          <div className="flex items-center gap-3 text-sm text-gray-300">
            <Brain className="w-4 h-4 text-purple-400" />
            AI-Powered Insights
          </div>
          <div className="flex items-center gap-3 text-sm text-gray-300">
            <Zap className="w-4 h-4 text-yellow-400" />
            Real-time Processing
          </div>
          <div className="flex items-center gap-3 text-sm text-gray-300">
            <RotateCcw className="w-4 h-4 text-green-400" />
            Answer Carousel
          </div>
          <div className="flex items-center gap-3 text-sm text-gray-300">
            <Play className="w-4 h-4 text-orange-400" />
            Resume Generation
          </div>
        </div>
      </div>
    </div>

    {/* Footer */}
    <div className="p-6 border-t border-gray-700">
      <div className="text-center">
        <div className="text-xs text-gray-400">
          Enhanced Research Assistant
        </div>
        <div className="text-xs text-gray-500 mt-1">
          v3.1 • Carousel UI
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════════════════
// ─── MAIN APPLICATION ──────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════────════════════════

export const EnhancedLangGraphChatApp: React.FC = () => {
  const [threadId, setThreadId] = useSearchParam('threadId');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isPreparingResponse, setIsPreparingResponse] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Configuration
  const apiUrl = 'http://localhost:2024';
  const assistantId = 'orchestrator';

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

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, showToolActivity, showGeneratingIndicator]);

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

  return (
    <div className="flex h-screen bg-gradient-to-br from-gray-50 via-white to-blue-50 font-sans">
      {/* Sidebar */}
      <Sidebar onNewThread={handleNewThread} />

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="bg-white/80 backdrop-blur-sm border-b border-gray-200 sticky top-0 z-20 shadow-sm">
          <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-bold text-gray-900">
                Enhanced Research Assistant
              </h1>
              <div className="h-6 w-px bg-gray-300"></div>
              <div className="text-sm text-gray-500">
                AI with carousel regeneration & human-in-the-loop
              </div>
            </div>

            {/* Status Indicator */}
            <div className="flex items-center gap-3">
              <div className={`w-2.5 h-2.5 rounded-full ${getStatusColor()}`} />
              <span className="text-sm font-medium text-gray-600">
                {getStatusText()}
              </span>
            </div>
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-5xl mx-auto px-6 py-6">
            {/* Welcome Screen */}
            {messages.length === 0 && !stream.isLoading && (
              <div className="text-center py-20">
                <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-2xl">
                  <Brain className="w-10 h-10 text-white" />
                </div>
                <h2 className="text-3xl font-bold text-gray-900 mb-3">
                  Enhanced AI Research Assistant
                </h2>
                <p className="text-gray-600 mb-8 max-w-md mx-auto text-lg leading-relaxed">
                  Advanced AI with carousel regeneration, resume capability, and human-in-the-loop collaboration.
                </p>
                <div className="flex justify-center gap-6 text-sm flex-wrap">
                  <div className="flex items-center gap-2 text-gray-500">
                    <Search className="w-4 h-4 text-blue-500" />
                    Web Research
                  </div>
                  <div className="flex items-center gap-2 text-gray-500">
                    <RotateCcw className="w-4 h-4 text-green-500" />
                    Carousel Versions
                  </div>
                  <div className="flex items-center gap-2 text-gray-500">
                    <Play className="w-4 h-4 text-orange-500" />
                    Resume Generation
                  </div>
                  <div className="flex items-center gap-2 text-gray-500">
                    <AlertCircle className="w-4 h-4 text-amber-500" />
                    Human Feedback
                  </div>
                </div>
              </div>
            )}

            {/* Messages */}
            {messages.map((message, index) => (
              <MessageBubble
                key={message.id}
                message={message}
                isLastMessage={index === messages.length - 1}
                onRegenerate={message.type === 'ai' ? () => handleRegenerate(message.id) : undefined}
                onResume={message.isIncomplete ? () => handleResume(message.id) : undefined}
                onHumanFeedback={message.needsHumanFeedback ? handleHumanFeedback : undefined}
                onEditMessage={message.type === 'human' ? handleEditMessage : undefined}
                onVersionChange={(index) => handleVersionChange(message.id, index)}
              />
            ))}

            {/* Activity Indicators */}
            {showPreparingIndicator && <PreparingIndicator />}
            {showToolActivity && <ToolActivityIndicator activity={toolActivity!} />}
            {showGeneratingIndicator && <GeneratingIndicator />}

            {/* Scroll anchor */}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Chat Input */}
        <ChatInput
          onSubmit={handleSubmit}
          isLoading={stream.isLoading}
          onStop={handleStop}
        />
      </div>
    </div>
  );
};

export default EnhancedLangGraphChatApp;

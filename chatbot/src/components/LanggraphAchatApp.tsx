import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
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
  Zap
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
}

// ═══════════════════════════════════════════════════════════════════════════════
// ─── MARKDOWN RENDERER ─────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════════

const MarkdownRenderer: React.FC<{ content: string }> = ({ content }) => {
  const formatMarkdown = (text: string): string => {
    return text
      // Headers (process from h6 to h1 to avoid conflicts)
      .replace(/^###### (.*$)/gim, '<h6 class="text-sm font-medium mt-4 mb-2 text-gray-700">$1</h6>')
      .replace(/^##### (.*$)/gim, '<h5 class="text-base font-medium mt-4 mb-2 text-gray-700">$1</h5>')
      .replace(/^#### (.*$)/gim, '<h4 class="text-base font-semibold mt-5 mb-2 text-gray-800">$1</h4>')
      .replace(/^### (.*$)/gim, '<h3 class="text-lg font-semibold mt-6 mb-3 text-gray-800">$1</h3>')
      .replace(/^## (.*$)/gim, '<h2 class="text-xl font-semibold mt-6 mb-3 text-gray-800">$1</h2>')
      .replace(/^# (.*$)/gim, '<h1 class="text-2xl font-bold mt-6 mb-4 text-gray-900">$1</h1>')
      // Bold text
      .replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold text-gray-900">$1</strong>')
      // Italic text
      .replace(/\*(.*?)\*/g, '<em class="italic text-gray-700">$1</em>')
      // Code blocks
      .replace(/```([\s\S]*?)```/g, '<pre class="bg-gray-50 border border-gray-200 p-4 rounded-lg mt-3 mb-3 overflow-x-auto text-sm"><code class="text-gray-800">$1</code></pre>')
      // Inline code
      .replace(/`([^`]*)`/g, '<code class="bg-gray-100 px-2 py-1 rounded text-sm font-mono text-gray-800">$1</code>')
      // Citations
      .replace(/\[(\d+)\]/g, '<sup class="text-blue-600 font-medium text-xs">[$1]</sup>')
      // Bullet points
      .replace(/^\* (.*$)/gim, '<li class="ml-4 mb-1 text-gray-700">$1</li>')
      .replace(/(<li.*<\/li>)/s, '<ul class="list-disc list-outside my-3 space-y-1">$1</ul>')
      // Numbered lists
      .replace(/^\d+\. (.*$)/gim, '<li class="ml-4 mb-1 text-gray-700">$1</li>')
      // Line breaks and paragraphs
      .replace(/\n\n/g, '</p><p class="mb-3 text-gray-700 leading-relaxed">')
      .replace(/\n/g, '<br>');
  };

  const htmlContent = formatMarkdown(content);
  
  return (
    <div 
      className="prose prose-sm max-w-none text-gray-700"
      dangerouslySetInnerHTML={{ 
        __html: `<div class="leading-relaxed">${htmlContent}</div>` 
      }} 
    />
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// ─── DATA PROCESSING ────────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════════

const processStreamMessages = (rawMessages: LangGraphMessage[] | undefined) => {
  if (!rawMessages) {
    return { 
      userMessages: [], 
      toolActivity: null, 
      hasActiveToolCalls: false 
    };
  }

  const userMessages: ChatMessage[] = [];
  let activeToolCalls: ToolCall[] = [];
  let hasActiveToolCalls = false;

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
          timestamp: new Date()
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

  return { userMessages, toolActivity, hasActiveToolCalls };
};

// ═══════════════════════════════════════════════════════════════════════════════
// ─── UI COMPONENTS ──────────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════════

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

const MessageBubble: React.FC<{ 
  message: ChatMessage; 
  isLastMessage?: boolean; 
}> = ({ message, isLastMessage = false }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy text:', err);
    }
  };

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
            {message.type === 'ai' ? (
              <MarkdownRenderer content={message.content} />
            ) : (
              <p className="whitespace-pre-wrap text-sm leading-relaxed">
                {message.content}
              </p>
            )}

            {/* Copy Button for AI messages */}
            {message.type === 'ai' && (
              <button
                onClick={handleCopy}
                className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600"
                title="Copy message"
              >
                {copied ? (
                  <Check className="w-4 h-4 text-green-500" />
                ) : (
                  <Copy className="w-4 h-4" />
                )}
              </button>
            )}
          </div>

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
        </div>
      </div>
    </div>

    {/* Footer */}
    <div className="p-6 border-t border-gray-700">
      <div className="text-center">
        <div className="text-xs text-gray-400">
          Advanced Research Assistant
        </div>
        <div className="text-xs text-gray-500 mt-1">
          v2.0 • LangGraph SDK
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════════════════════════════════════════
// ─── MAIN APPLICATION ──────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════════

export const LangGraphChatApp: React.FC = () => {
  const [threadId, setThreadId] = useSearchParam('threadId');
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
  });

  // Process messages for display
  const { userMessages, toolActivity, hasActiveToolCalls } = useMemo(
    () => processStreamMessages(stream.messages),
    [stream.messages]
  );

  // UI state logic
  const isGenerating = stream.values?.is_generating || false;
  const showToolActivity = hasActiveToolCalls && userMessages.length > 0;
  const showGeneratingIndicator = isGenerating && !showToolActivity && userMessages.length > 0;

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [userMessages, showToolActivity, showGeneratingIndicator]);

  // Event handlers
  const handleSubmit = (input: string) => {
    stream.submit({ 
      messages: [{ type: "human", content: input }],
      streamResumable: true
    });
  };

  const handleNewThread = () => {
    setThreadId(null);
  };

  const getStatusText = (): string => {
    if (showToolActivity) return 'Researching';
    if (showGeneratingIndicator) return 'Generating';
    if (stream.isLoading) return 'Processing';
    return 'Ready';
  };

  const getStatusColor = (): string => {
    if (showToolActivity || showGeneratingIndicator || stream.isLoading) {
      return 'bg-green-500 animate-pulse';
    }
    return 'bg-gray-400';
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
                Research Assistant
              </h1>
              <div className="h-6 w-px bg-gray-300"></div>
              <div className="text-sm text-gray-500">
                AI-powered research and analysis
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
            {userMessages.length === 0 && !stream.isLoading && (
              <div className="text-center py-20">
                <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-2xl">
                  <Brain className="w-10 h-10 text-white" />
                </div>
                <h2 className="text-3xl font-bold text-gray-900 mb-3">
                  AI Research Assistant
                </h2>
                <p className="text-gray-600 mb-8 max-w-md mx-auto text-lg leading-relaxed">
                  Ask me anything and I'll research, analyze, and provide comprehensive answers using advanced AI tools.
                </p>
                <div className="flex justify-center gap-6 text-sm">
                  <div className="flex items-center gap-2 text-gray-500">
                    <Search className="w-4 h-4 text-blue-500" />
                    Web Research
                  </div>
                  <div className="flex items-center gap-2 text-gray-500">
                    <Brain className="w-4 h-4 text-purple-500" />
                    AI Analysis
                  </div>
                  <div className="flex items-center gap-2 text-gray-500">
                    <Zap className="w-4 h-4 text-yellow-500" />
                    Real-time Results
                  </div>
                </div>
              </div>
            )}

            {/* Messages */}
            {userMessages.map((message, index) => (
              <MessageBubble
                key={message.id}
                message={message}
                isLastMessage={index === userMessages.length - 1}
              />
            ))}

            {/* Activity Indicators */}
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
          onStop={stream.stop}
        />
      </div>
    </div>
  );
};

export default LangGraphChatApp;
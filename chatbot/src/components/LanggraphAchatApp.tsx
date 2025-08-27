import React, { useRef, useEffect, useState, useCallback } from 'react';
import { useStream } from "@langchain/langgraph-sdk/react";
import type { Message as LangGraphMessage } from "@langchain/langgraph-sdk";
import { Bot, Send, Square, RefreshCw, Edit3, Loader, Globe, Search, CheckCircle, AlertCircle, User, Copy, Check, ChevronLeft, ChevronRight, Plus, MessageSquare } from 'lucide-react';

// Custom hook for URL search params
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
    if (newValue == null) {
      url.searchParams.delete(key);
    } else {
      url.searchParams.set(key, newValue);
    }
    window.history.pushState({}, '', url.toString());
  }, [key]);

  return [value, update];
}

// Types for the application
interface Message extends LangGraphMessage {
  id: string;
  content: string;
  type: 'human' | 'ai';
  timestamp?: Date;
  isStreaming?: boolean;
  branches?: string[];
  currentBranchIndex?: number;
}

interface LoadingMessage {
  message: string;
  level: 'info' | 'success' | 'warning' | 'error' | 'debug';
  timestamp: string;
  language?: string;
}

interface Thread {
  id: string;
  title: string;
  lastMessage?: string;
  createdAt: Date;
}

// Progress Steps Component - Now positioned after AI messages
const ProgressSteps: React.FC<{ messages: LoadingMessage[] }> = ({ messages }) => {
  const getIcon = (level: string) => {
    switch (level) {
      case 'success': return <CheckCircle className="w-3 h-3 text-green-500" />;
      case 'warning': return <AlertCircle className="w-3 h-3 text-yellow-500" />;
      case 'error': return <AlertCircle className="w-3 h-3 text-red-500" />;
      case 'info': default: return <Search className="w-3 h-3 text-blue-500" />;
    }
  };

  if (!messages || messages.length === 0) return null;

  return (
    <div className="flex justify-start mb-4">
      <div className="max-w-3xl flex gap-3">
        {/* Avatar spacer */}
        <div className="w-8 h-8 flex-shrink-0" />
        
        {/* Progress content */}
        <div className="bg-blue-50 border border-blue-100 rounded-lg p-3 flex-1">
          <div className="flex items-center gap-2 mb-2">
            <Loader className="w-4 h-4 animate-spin text-blue-600" />
            <span className="text-sm font-medium text-blue-800">Researching your query...</span>
          </div>
          <div className="space-y-1.5 max-h-24 overflow-y-auto">
            {messages.slice(-4).map((msg, idx) => (
              <div key={idx} className="flex items-center gap-2 text-xs text-gray-700">
                {getIcon(msg.level)}
                <span className="truncate">{msg.message}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

// Copy Button Component
const CopyButton: React.FC<{ text: string }> = ({ text }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  };

  return (
    <button
      onClick={handleCopy}
      className="p-1 hover:bg-gray-100 rounded transition-colors opacity-0 group-hover:opacity-100"
      title={copied ? 'Copied!' : 'Copy message'}
    >
      {copied ? (
        <Check className="w-3 h-3 text-green-600" />
      ) : (
        <Copy className="w-3 h-3 text-gray-500" />
      )}
    </button>
  );
};

// Branch Navigation Component
const BranchNavigation: React.FC<{
  message: Message;
  onBranchChange: (messageId: string, branchIndex: number) => void;
}> = ({ message, onBranchChange }) => {
  if (!message.branches || message.branches.length <= 1) return null;

  const currentIndex = message.currentBranchIndex || 0;
  const totalBranches = message.branches.length;

  return (
    <div className="flex items-center gap-1 mt-2 text-xs text-gray-500 opacity-0 group-hover:opacity-100 transition-opacity">
      <button
        onClick={() => onBranchChange(message.id, Math.max(0, currentIndex - 1))}
        disabled={currentIndex === 0}
        className="p-1 hover:bg-gray-100 rounded disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <ChevronLeft className="w-3 h-3" />
      </button>
      <span className="px-1">{currentIndex + 1} of {totalBranches}</span>
      <button
        onClick={() => onBranchChange(message.id, Math.min(totalBranches - 1, currentIndex + 1))}
        disabled={currentIndex === totalBranches - 1}
        className="p-1 hover:bg-gray-100 rounded disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <ChevronRight className="w-3 h-3" />
      </button>
    </div>
  );
};

// Message Bubble Component
const MessageBubble: React.FC<{
  message: Message;
  onEdit?: (message: Message, content: string) => void;
  onRegenerate?: (message: Message) => void;
  onBranchChange?: (messageId: string, branchIndex: number) => void;
  isLastMessage?: boolean;
}> = ({ message, onEdit, onRegenerate, onBranchChange, isLastMessage = false }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(message.content);

  const handleEdit = () => {
    if (onEdit && editContent.trim() !== message.content) {
      onEdit(message, editContent.trim());
    }
    setIsEditing(false);
  };

  const displayContent = message.branches && message.currentBranchIndex !== undefined
    ? message.branches[message.currentBranchIndex]
    : message.content;

    if (message.type !== 'human' && message.type !== 'ai') {
        return null;
    }

  return (
    <div className={`flex ${message.type === 'human' ? 'justify-end' : 'justify-start'} mb-4 group`}>
      <div className={`max-w-3xl flex gap-3 ${message.type === 'human' ? 'flex-row-reverse' : 'flex-row'}`}>
        {/* Avatar */}
        <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
          message.type === 'human' 
            ? 'bg-gray-700' 
            : 'bg-blue-600'
        }`}>
          {message.type === 'human' ? (
            <User className="w-4 h-4 text-white" />
          ) : (
            <Bot className="w-4 h-4 text-white" />
          )}
        </div>

        {/* Message Content */}
        <div className="flex-1">
          {isEditing && message.type === 'human' ? (
            <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                className="w-full p-3 border border-gray-200 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                rows={3}
                autoFocus
              />
              <div className="flex gap-2 mt-3">
                <button
                  onClick={handleEdit}
                  className="px-3 py-1.5 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700 transition-colors"
                >
                  Save
                </button>
                <button
                  onClick={() => {
                    setIsEditing(false);
                    setEditContent(message.content);
                  }}
                  className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-md text-sm hover:bg-gray-200 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className={`rounded-lg px-4 py-3 ${
              message.type === 'human' 
                ? 'bg-blue-600 text-white ml-12' 
                : 'bg-white border border-gray-200 shadow-sm'
            }`}>
              {message.isStreaming ? (
                <div className="flex items-center gap-2">
                  <Loader className="w-4 h-4 animate-spin text-blue-600" />
                  <span className="text-sm text-gray-500">Generating response...</span>
                </div>
              ) : message.type === 'ai' ? (
                <div 
                  className="prose prose-sm max-w-none prose-headings:font-semibold prose-headings:text-gray-900 prose-p:text-gray-800 prose-p:leading-relaxed prose-li:text-gray-800 prose-strong:text-gray-900"
                  dangerouslySetInnerHTML={{ __html: formatMarkdown(displayContent) }} 
                />
              ) : (
                <p className="whitespace-pre-wrap text-sm leading-relaxed">{displayContent}</p>
              )}
              
              {/* Action Buttons */}
              {!message.isStreaming && (
                <div className="flex items-center gap-1 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  {message.type === 'human' && onEdit && isLastMessage && (
                    <button
                      onClick={() => setIsEditing(true)}
                      className="p-1 hover:bg-blue-700 rounded transition-colors"
                      title="Edit message"
                    >
                      <Edit3 className="w-3 h-3" />
                    </button>
                  )}
                  {message.type === 'ai' && (
                    <>
                      <CopyButton text={displayContent} />
                      {onRegenerate && isLastMessage && (
                        <button
                          onClick={() => onRegenerate(message)}
                          className="p-1 hover:bg-gray-100 rounded transition-colors"
                          title="Regenerate response"
                        >
                          <RefreshCw className="w-3 h-3 text-gray-500" />
                        </button>
                      )}
                    </>
                  )}
                </div>
              )}

              {/* Branch Navigation */}
              {message.type === 'ai' && onBranchChange && (
                <BranchNavigation message={message} onBranchChange={onBranchChange} />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Improved markdown formatting
const formatMarkdown = (content: string): string => {
  const stringContent = typeof content === 'string' ? content : String(content);
  
  return stringContent
    // Headers
    .replace(/^### (.*$)/gm, '<h3 class="text-base font-semibold mt-4 mb-2 text-gray-900">$1</h3>')
    .replace(/^## (.*$)/gm, '<h2 class="text-lg font-semibold mt-5 mb-3 text-gray-900">$1</h2>')
    .replace(/^# (.*$)/gm, '<h1 class="text-xl font-bold mt-6 mb-4 text-gray-900">$1</h1>')
    
    // Text formatting
    .replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold text-gray-900">$1</strong>')
    .replace(/\*(.*?)\*/g, '<em class="italic">$1</em>')
    .replace(/`([^`]+)`/g, '<code class="bg-gray-100 px-1.5 py-0.5 rounded text-sm font-mono text-gray-800">$1</code>')
    
    // Lists
    .replace(/^- (.*$)/gm, '<li class="ml-4 mb-1">$1</li>')
    .replace(/^\d+\. (.*$)/gm, '<li class="ml-4 mb-1">$1</li>')
    
    // Citations
    .replace(/\[(\d+)\]/g, '<sup class="text-blue-600 text-xs">[$1]</sup>')
    
    // Paragraphs
    .split('\n\n')
    .map(paragraph => {
      if (paragraph.includes('<li')) {
        return '<ul class="list-disc list-inside space-y-1 mb-3">' + paragraph + '</ul>';
      }
      if (paragraph.includes('<h')) {
        return paragraph;
      }
      return paragraph ? `<p class="mb-3 leading-relaxed">${paragraph}</p>` : '';
    })
    .join('');
};

// Chat Input Component
const ChatInput: React.FC<{
  onSubmit: (message: string) => void;
  isLoading: boolean;
  onStop: () => void;
}> = ({ onSubmit, isLoading, onStop }) => {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    
    onSubmit(input.trim());
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    
    // Auto-resize textarea
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  };

  return (
    <div className="border-t bg-white p-4 sticky bottom-0">
      <div className="max-w-4xl mx-auto">
        <div className="flex gap-3 items-end">
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder="Message LangGraph Research Assistant..."
              className="w-full border border-gray-300 rounded-xl px-4 py-3 resize-none min-h-[48px] max-h-32 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent pr-12"
              rows={1}
            />
          </div>
          {isLoading ? (
            <button
              type="button"
              onClick={onStop}
              className="p-3 bg-red-500 text-white rounded-xl hover:bg-red-600 transition-colors flex items-center justify-center"
              title="Stop generation"
            >
              <Square className="w-4 h-4" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!input.trim()}
              className="p-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center justify-center"
              title="Send message"
            >
              <Send className="w-4 h-4" />
            </button>
          )}
        </div>
        <div className="flex items-center justify-between mt-2 text-xs text-gray-500">
          <span>Press Enter to send, Shift+Enter for new line</span>
        </div>
      </div>
    </div>
  );
};

// Improved Sidebar Component
const Sidebar: React.FC<{
  threadId: string | null;
  onNewThread: () => void;
  recentThreads: Thread[];
  onThreadSelect: (threadId: string) => void;
}> = ({ threadId, onNewThread, recentThreads, onThreadSelect }) => {
  return (
    <div className="w-64 bg-gray-900 text-white flex flex-col h-full">
      <div className="p-4">
        <button
          onClick={onNewThread}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2.5 px-4 rounded-lg mb-6 transition-colors flex items-center gap-2 font-medium"
        >
          <Plus className="w-4 h-4" />
          New Research
        </button>
      </div>
      
      <div className="flex-1 overflow-y-auto px-4">
        <h3 className="text-xs font-semibold text-gray-400 mb-3 uppercase tracking-wide">Recent Conversations</h3>
        <div className="space-y-1">
          {recentThreads.map((thread) => (
            <div
              key={thread.id}
              onClick={() => onThreadSelect(thread.id)}
              className={`p-3 rounded-lg cursor-pointer transition-colors ${
                threadId === thread.id 
                  ? 'bg-blue-600' 
                  : 'hover:bg-gray-800'
              }`}
            >
              <div className="flex items-start gap-2">
                <MessageSquare className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm truncate text-white">{thread.title}</div>
                  {thread.lastMessage && (
                    <div className="text-xs text-gray-400 mt-1 truncate">
                      {thread.lastMessage}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
      
      <div className="p-4 border-t border-gray-800">
        <div className="text-xs text-gray-400 text-center">
          LangGraph Research Assistant
        </div>
      </div>
    </div>
  );
};

// Interrupt Dialog Component
const InterruptDialog: React.FC<{
  interrupt: any;
  onResume: (value?: any) => void;
  onCancel: () => void;
  isOpen: boolean;
}> = ({ interrupt, onResume, onCancel, isOpen }) => {
  if (!isOpen || !interrupt) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl p-6 max-w-md w-full mx-4 shadow-xl">
        <h3 className="text-lg font-semibold mb-4 text-gray-900">Clarification Needed</h3>
        <p className="text-gray-700 mb-6 leading-relaxed">{interrupt.value}</p>
        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Start Over
          </button>
          <button
            onClick={() => onResume()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Continue
          </button>
        </div>
      </div>
    </div>
  );
};

// Main integrated chat application
export const LangGraphChatApp: React.FC = () => {
  const [threadId, setThreadId] = useSearchParam('threadId');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  const apiUrl = 'http://localhost:2024';
  const assistantId = 'orchestrator';

  // Use the official useStream hook
  const thread = useStream<{ 
    messages: LangGraphMessage[], 
    loading_messages?: LoadingMessage[],
    detected_language?: string 
  }>({
    apiUrl,
    assistantId,
    threadId: threadId || undefined,
    onThreadId: setThreadId,
    messagesKey: "messages",
    reconnectOnMount: true,
  });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [thread.messages, thread.values?.loading_messages]);

  const handleSubmit = (message: string) => {
    if (!message.trim()) return;
    
    thread.submit({ 
      messages: [{ type: "human", content: message }] 
    });
  };

  const handleEdit = (message: Message, content: string) => {
    const messageIndex = thread.messages.findIndex(m => m.id === message.id);
    if (messageIndex === -1) return;

    // Create a new branch from the checkpoint before this message
    const metadata = thread.getMessagesMetadata(message);
    const parentCheckpoint = metadata?.firstSeenState?.parent_checkpoint;

    thread.submit(
      { messages: [{ type: "human", content }] },
      { checkpoint: parentCheckpoint }
    );
  };

  const handleRegenerate = (message: Message) => {
    const metadata = thread.getMessagesMetadata(message);
    const parentCheckpoint = metadata?.firstSeenState?.parent_checkpoint;

    thread.submit(
      undefined,
      { checkpoint: parentCheckpoint }
    );
  };

  const handleBranchChange = (messageId: string, branchIndex: number) => {
    const branches = thread.experimental_branchTree;
    if (branches) {
      thread.setBranch(branches[branchIndex]);
    }
  };

  const handleNewThread = () => {
    setThreadId(null);
  };

  const handleThreadSelect = (selectedThreadId: string) => {
    if (selectedThreadId !== threadId) {
      setThreadId(selectedThreadId);
    }
  };

  const handleResumeInterrupt = () => {
    thread.submit(undefined, { command: { resume: true } });
  };

  const handleCancelInterrupt = () => {
    setThreadId(null);
  };

  // Transform LangGraph messages to our Message type
    const messages: Message[] = thread.messages
    .filter(msg => {
        // Exclude tool messages and internal system messages
        return msg.type === 'human' || 
            msg.type === 'ai' || 
            msg.type === 'system'; // Keep system messages if needed
    })
    .map(msg => ({
        ...msg,
        type: msg.type as 'human' | 'ai' | 'system',
        timestamp: new Date(),
        content: typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content),
    }));

  // Mock recent threads data
  const recentThreads: Thread[] = [
    {
      id: 'thread-1',
      title: 'Climate Change Research',
      lastMessage: 'Thanks for the comprehensive analysis on renewable energy trends.',
      createdAt: new Date()
    },
    {
      id: 'thread-2', 
      title: 'Machine Learning Basics',
      lastMessage: 'The explanation of neural networks was very helpful.',
      createdAt: new Date(Date.now() - 86400000)
    },
    {
      id: 'thread-3',
      title: 'Economic Data Analysis', 
      lastMessage: 'Could you analyze the latest GDP figures?',
      createdAt: new Date(Date.now() - 172800000)
    }
  ];

  const lastAiMessageIndex = messages.length > 0 
    ? Math.max(...messages.map((msg, idx) => msg.type === 'ai' ? idx : -1).filter(idx => idx >= 0))
    : -1;

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar 
        threadId={thread.threadId}
        onNewThread={handleNewThread}
        recentThreads={recentThreads}
        onThreadSelect={handleThreadSelect}
      />
      
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="bg-white border-b p-4 sticky top-0 z-10">
          <div className="max-w-4xl mx-auto">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-lg font-semibold text-gray-900">Research Assistant</h1>
                <div className="flex items-center gap-4 text-sm text-gray-500 mt-1">
                  <span className="flex items-center gap-1.5">
                    <Globe className="w-3 h-3" />
                    {thread.values?.detected_language || 'English'}
                  </span>
                  {thread.threadId && (
                    <span className="text-xs bg-gray-100 px-2 py-1 rounded-full">
                      {thread.threadId.slice(0, 8)}...
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${thread.isLoading ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
                <span className="text-sm text-gray-500">
                  {thread.isLoading ? 'Researching...' : 'Ready'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-4xl mx-auto p-4">
            {/* Empty State */}
            {messages.length === 0 && !thread.isLoading && (
              <div className="text-center py-16">
                <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Bot className="w-8 h-8 text-blue-600" />
                </div>
                <h2 className="text-xl font-semibold text-gray-900 mb-2">
                  AI Research Assistant
                </h2>
                <p className="text-gray-600 mb-6 max-w-md mx-auto">
                  Ask me anything and I'll search multiple sources to provide comprehensive, cited answers in any language.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-2xl mx-auto text-sm">
                  <div className="bg-white p-4 rounded-lg border border-gray-200">
                    <Search className="w-5 h-5 text-blue-600 mb-2" />
                    <div className="font-medium text-gray-900 mb-1">Multi-Source Search</div>
                    <div className="text-gray-600">Tavily, Wikipedia, DuckDuckGo</div>
                  </div>
                  <div className="bg-white p-4 rounded-lg border border-gray-200">
                    <Globe className="w-5 h-5 text-green-600 mb-2" />
                    <div className="font-medium text-gray-900 mb-1">Multilingual</div>
                    <div className="text-gray-600">Auto-detects and optimizes</div>
                  </div>
                  <div className="bg-white p-4 rounded-lg border border-gray-200">
                    <CheckCircle className="w-5 h-5 text-purple-600 mb-2" />
                    <div className="font-medium text-gray-900 mb-1">Cited Sources</div>
                    <div className="text-gray-600">Reliable, referenced answers</div>
                  </div>
                </div>
              </div>
            )}
            
            {/* Chat Messages */}
            {messages.map((message, index) => (
              <React.Fragment key={message.id}>
                <MessageBubble
                  message={message}
                  onEdit={handleEdit}
                  onRegenerate={handleRegenerate}
                  onBranchChange={handleBranchChange}
                  isLastMessage={index === messages.length - 1}
                />
                
                {/* Show progress steps after the last AI message when loading */}
                {index === lastAiMessageIndex && 
                 thread.isLoading && 
                 thread.values?.loading_messages && 
                 thread.values.loading_messages.length > 0 && (
                  <ProgressSteps messages={thread.values.loading_messages} />
                )}
              </React.Fragment>
            ))}
            
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Area */}
        <ChatInput
          onSubmit={handleSubmit}
          isLoading={thread.isLoading}
          onStop={thread.stop}
        />
      </div>

      {/* Interrupt Dialog */}
      <InterruptDialog
        interrupt={thread.interrupt}
        onResume={handleResumeInterrupt}
        onCancel={handleCancelInterrupt}
        isOpen={!!thread.interrupt}
      />
    </div>
  );
};

export default LangGraphChatApp
import React, { useRef, useEffect, useState, useCallback } from 'react';
import { useStream } from "@langchain/langgraph-sdk/react";
import type { Message as LangGraphMessage } from "@langchain/langgraph-sdk";
import { Bot, Send, Square, RefreshCw, Edit3, Loader, Globe, Search, CheckCircle, AlertCircle, User, Copy, Check, ChevronLeft, ChevronRight } from 'lucide-react';

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

// Loading Indicator Component
const LoadingIndicator: React.FC<{ messages: LoadingMessage[] }> = ({ messages }) => {
  const getIcon = (level: string) => {
    switch (level) {
      case 'success': return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'warning': return <AlertCircle className="w-4 h-4 text-yellow-500" />;
      case 'error': return <AlertCircle className="w-4 h-4 text-red-500" />;
      case 'info': default: return <Search className="w-4 h-4 text-blue-500" />;
    }
  };

  return (
    <div className="flex justify-start mb-6">
      <div className="max-w-3xl">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center">
            <Bot className="w-4 h-4 text-white" />
          </div>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex-1">
            <div className="flex items-center gap-2 mb-2">
              <Loader className="w-4 h-4 animate-spin text-blue-600" />
              <span className="font-medium text-blue-800">Researching...</span>
            </div>
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {messages.slice(-5).map((msg, idx) => (
                <div key={idx} className="flex items-center gap-2 text-sm">
                  {getIcon(msg.level)}
                  <span className="text-gray-700">{msg.message}</span>
                </div>
              ))}
            </div>
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
      className="p-1 hover:bg-gray-100 rounded transition-colors"
      title={copied ? 'Copied!' : 'Copy message'}
    >
      {copied ? (
        <Check className="w-4 h-4 text-green-600" />
      ) : (
        <Copy className="w-4 h-4 text-gray-600" />
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
    <div className="flex items-center gap-2 mt-2 text-xs text-gray-500">
      <button
        onClick={() => onBranchChange(message.id, Math.max(0, currentIndex - 1))}
        disabled={currentIndex === 0}
        className="p-1 hover:bg-gray-100 rounded disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <ChevronLeft className="w-3 h-3" />
      </button>
      <span>{currentIndex + 1} / {totalBranches}</span>
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

  return (
    <div className={`flex ${message.type === 'human' ? 'justify-end' : 'justify-start'} mb-6`}>
      <div className={`max-w-3xl flex gap-3 ${message.type === 'human' ? 'flex-row-reverse' : 'flex-row'}`}>
        {/* Avatar */}
        <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
          message.type === 'human' 
            ? 'bg-gray-600' 
            : 'bg-blue-600'
        }`}>
          {message.type === 'human' ? (
            <User className="w-4 h-4 text-white" />
          ) : (
            <Bot className="w-4 h-4 text-white" />
          )}
        </div>

        {/* Message Content */}
        <div className={`px-4 py-2 rounded-lg relative ${
          message.type === 'human' 
            ? 'bg-gray-600 text-white' 
            : 'bg-white border shadow-sm'
        }`}>
          {isEditing && message.type === 'human' ? (
            <div className="space-y-2">
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                className="w-full p-2 border rounded resize-none text-black"
                rows={3}
              />
              <div className="flex gap-2">
                <button
                  onClick={handleEdit}
                  className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700"
                >
                  Save
                </button>
                <button
                  onClick={() => {
                    setIsEditing(false);
                    setEditContent(message.content);
                  }}
                  className="px-3 py-1 bg-gray-600 text-white rounded text-sm hover:bg-gray-700"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className={`prose max-w-none ${message.type === 'human' ? 'prose-invert' : ''}`}>
                {message.isStreaming ? (
                  <div className="flex items-center gap-2 mb-2">
                    <Loader className="w-4 h-4 animate-spin text-blue-600" />
                    <span className="text-sm text-gray-500">Generating response...</span>
                  </div>
                ) : message.type === 'ai' ? (
                  <div dangerouslySetInnerHTML={{ __html: formatMarkdown(displayContent) }} />
                ) : (
                  <p className="whitespace-pre-wrap">{displayContent}</p>
                )}
              </div>
              
              {/* Action Buttons */}
              <div className="flex items-center gap-2 mt-2">
                {message.type === 'human' && onEdit && isLastMessage && (
                  <button
                    onClick={() => setIsEditing(true)}
                    className="p-1 hover:bg-gray-700 rounded transition-colors"
                    title="Edit message"
                  >
                    <Edit3 className="w-4 h-4" />
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
                        <RefreshCw className="w-4 h-4 text-gray-600" />
                      </button>
                    )}
                  </>
                )}
              </div>

              {/* Branch Navigation */}
              {message.type === 'ai' && onBranchChange && (
                <BranchNavigation message={message} onBranchChange={onBranchChange} />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

// Basic markdown formatting
const formatMarkdown = (content: string): string => {
  const stringContent = typeof content === 'string' ? content : String(content);
  
  return stringContent
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/^## (.*$)/gm, '<h2 class="text-xl font-bold mt-6 mb-3">$1</h2>')
    .replace(/^### (.*$)/gm, '<h3 class="text-lg font-semibold mt-4 mb-2">$1</h3>')
    .replace(/^\- (.*$)/gm, '<li class="ml-4">$1</li>')
    .replace(/\[(\d+)\]/g, '<sup class="text-blue-600">[$1]</sup>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/^(.*)$/gm, '<p>$1</p>')
    .replace(/<p><li/g, '<ul><li')
    .replace(/li><\/p>/g, 'li></ul>');
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
    <div className="border-t bg-white p-4">
      <div className="max-w-4xl mx-auto">
        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder="Ask me anything..."
              className="w-full border rounded-lg px-4 py-3 resize-none min-h-[44px] max-h-32 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              rows={1}
            />
          </div>
          {isLoading ? (
            <button
              type="button"
              onClick={onStop}
              className="px-4 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
              title="Stop generation"
            >
              <Square className="w-4 h-4" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!input.trim()}
              className="px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
              title="Send message"
            >
              <Send className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

// Sidebar Component
const Sidebar: React.FC<{
  threadId: string | null;
  onNewThread: () => void;
  recentThreads: Thread[];
  onThreadSelect: (threadId: string) => void;
}> = ({ threadId, onNewThread, recentThreads, onThreadSelect }) => {
  return (
    <div className="w-64 bg-gray-900 text-white p-4 flex flex-col">
      <button
        onClick={onNewThread}
        className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded mb-6 transition-colors"
      >
        New Research
      </button>
      
      <div className="flex-1 overflow-y-auto">
        <h3 className="text-sm font-semibold text-gray-400 mb-3">Recent Threads</h3>
        <div className="space-y-2">
          {recentThreads.map((thread) => (
            <div
              key={thread.id}
              onClick={() => onThreadSelect(thread.id)}
              className={`p-3 rounded cursor-pointer transition-colors ${
                threadId === thread.id 
                  ? 'bg-blue-600' 
                  : 'hover:bg-gray-800'
              }`}
            >
              <div className="font-medium text-sm truncate">{thread.title}</div>
              {thread.lastMessage && (
                <div className="text-xs text-gray-400 mt-1 truncate">
                  {thread.lastMessage}
                </div>
              )}
            </div>
          ))}
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
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md mx-4">
        <h3 className="text-lg font-semibold mb-4">Clarification Needed</h3>
        <p className="text-gray-700 mb-6">{interrupt.value}</p>
        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-gray-600 border rounded hover:bg-gray-50"
          >
            Start Over
          </button>
          <button
            onClick={() => onResume()}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
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
  }, [thread.messages]);

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
  const messages: Message[] = thread.messages.map(msg => ({
    ...msg,
    type: msg.type as 'human' | 'ai',
    timestamp: new Date(),
  }));

  // Mock recent threads data
  const recentThreads: Thread[] = [
    {
      id: 'thread-1',
      title: 'Previous Research Query',
      lastMessage: 'Thanks for the detailed analysis!',
      createdAt: new Date()
    },
    {
      id: 'thread-2', 
      title: 'Language Translation Request',
      lastMessage: 'The translation was accurate and helpful',
      createdAt: new Date(Date.now() - 86400000)
    }
  ];

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
        <div className="bg-white border-b p-4">
          <div className="max-w-4xl mx-auto">
            <h1 className="text-xl font-semibold text-gray-800">LangGraph Research Assistant</h1>
            <div className="flex items-center gap-4 text-sm text-gray-600 mt-1">
              <span className="flex items-center gap-1">
                <Globe className="w-4 h-4" />
                Language: {thread.values?.detected_language || 'English'}
              </span>
              {thread.threadId && (
                <span>Thread: {thread.threadId.slice(0, 8)}...</span>
              )}
              <span className="flex items-center gap-1">
                <div className={`w-2 h-2 rounded-full ${thread.isLoading ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
                {thread.isLoading ? 'Researching...' : 'Ready'}
              </span>
            </div>
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-4">
          <div className="max-w-4xl mx-auto">
            {/* Loading Messages */}
            {thread.isLoading && thread.values?.loading_messages && thread.values.loading_messages.length > 0 && (
              <LoadingIndicator messages={thread.values.loading_messages} />
            )}
            
            {/* Chat Messages */}
            {messages.map((message, index) => (
              <MessageBubble
                key={message.id}
                message={message}
                onEdit={handleEdit}
                onRegenerate={handleRegenerate}
                onBranchChange={handleBranchChange}
                isLastMessage={index === messages.length - 1}
              />
            ))}
            
            {/* Empty State */}
            {messages.length === 0 && !thread.isLoading && (
              <div className="text-center py-12">
                <Bot className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h2 className="text-xl font-semibold text-gray-600 mb-2">
                  Multilingual Research Assistant Ready
                </h2>
                <p className="text-gray-500 mb-4">
                  Ask me anything in any language and I'll search multiple sources to provide comprehensive answers.
                </p>
                <div className="text-sm text-gray-400 space-y-1">
                  <p>• Automatic language detection and optimization</p>
                  <p>• Uses Tavily, Wikipedia, and DuckDuckGo</p>
                  <p>• Provides cited answers with sources</p>
                  <p>• Supports clarification requests</p>
                </div>
              </div>
            )}
            
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

export default LangGraphChatApp;
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useStream } from '@langchain/langgraph-sdk/react';
import type { Message } from '@langchain/langgraph-sdk';
import { 
  Send, 
  Square, 
  MessageSquare, 
  Edit3, 
  RefreshCw, 
  ChevronLeft, 
  ChevronRight,
  Copy,
  Check,
  AlertCircle,
  Loader2,
  Plus,
  Search,
  Settings,
  User,
  Bot
} from 'lucide-react';

// Types for your LangGraph agent state
interface AgentState {
  messages: Message[];
  needs_clarification?: boolean;
  search_results?: Array<{
    title: string;
    content: string;
    url: string;
    source: string;
  }>;
  detected_language?: string;
  loading_messages?: Array<{
    message: string;
    level: string;
    timestamp: string;
  }>;
  user_query?: string;
  search_queries?: string[];
  search_complete?: boolean;
}

interface LoadingMessage {
  message: string;
  level: 'info' | 'success' | 'warning' | 'error' | 'debug';
  timestamp: string;
}

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

// Components
const LoadingIndicator: React.FC<{ messages: LoadingMessage[] }> = ({ messages }) => {
  const latestMessage = messages[messages.length - 1];
  
  if (!latestMessage) return null;

  const getLevelIcon = (level: string) => {
    switch (level) {
      case 'success': return <Check className="w-3 h-3 text-green-500" />;
      case 'warning': return <AlertCircle className="w-3 h-3 text-yellow-500" />;
      case 'error': return <AlertCircle className="w-3 h-3 text-red-500" />;
      default: return <Loader2 className="w-3 h-3 text-blue-500 animate-spin" />;
    }
  };

  return (
    <div className="flex items-center gap-2 text-sm text-gray-600 px-4 py-2 bg-gray-50 rounded-lg mb-4">
      {getLevelIcon(latestMessage.level)}
      <span>{latestMessage.message}</span>
    </div>
  );
};

const MessageContent: React.FC<{ content: string }> = ({ content }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group">
      <div className="prose prose-sm max-w-none">
        <div className="whitespace-pre-wrap">{content}</div>
      </div>
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-gray-100"
        title="Copy message"
      >
        {copied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
      </button>
    </div>
  );
};

const BranchSwitcher: React.FC<{
  branch?: string;
  branchOptions?: string[];
  onSelect: (branch: string) => void;
}> = ({ branch, branchOptions, onSelect }) => {
  if (!branchOptions || !branch || branchOptions.length <= 1) return null;
  
  const index = branchOptions.indexOf(branch);

  return (
    <div className="flex items-center gap-1 text-xs text-gray-500 mt-2">
      <button
        type="button"
        onClick={() => {
          const prevBranch = branchOptions[index - 1];
          if (prevBranch) onSelect(prevBranch);
        }}
        disabled={index === 0}
        className="p-1 rounded hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <ChevronLeft className="w-3 h-3" />
      </button>
      <span className="px-2">
        {index + 1} / {branchOptions.length}
      </span>
      <button
        type="button"
        onClick={() => {
          const nextBranch = branchOptions[index + 1];
          if (nextBranch) onSelect(nextBranch);
        }}
        disabled={index === branchOptions.length - 1}
        className="p-1 rounded hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <ChevronRight className="w-3 h-3" />
      </button>
    </div>
  );
};

const EditMessage: React.FC<{
  message: Message;
  onEdit: (content: string) => void;
}> = ({ message, onEdit }) => {
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState(message.content as string);

  const handleSubmit = () => {
    onEdit(editContent);
    setEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && e.ctrlKey) {
      handleSubmit();
    }
    if (e.key === 'Escape') {
      setEditing(false);
    }
  };

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => setEditing(true)}
        className="p-1 rounded hover:bg-gray-100 opacity-0 group-hover:opacity-100 transition-opacity"
        title="Edit message"
      >
        <Edit3 className="w-4 h-4" />
      </button>
    );
  }

  return (
    <div className="mt-2 space-y-2">
      <textarea
        value={editContent}
        onChange={(e) => setEditContent(e.target.value)}
        onKeyDown={handleKeyDown}
        className="w-full p-2 border rounded-lg resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        rows={3}
        autoFocus
        placeholder="Press Ctrl+Enter to save, Escape to cancel"
      />
      <div className="flex gap-2">
        <button
          type="button"
          onClick={handleSubmit}
          className="px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm"
        >
          Save
        </button>
        <button
          type="button"
          onClick={() => setEditing(false)}
          className="px-3 py-1 border rounded hover:bg-gray-50 text-sm"
        >
          Cancel
        </button>
      </div>
    </div>
  );
};

const MessageBubble: React.FC<{
  message: Message;
  thread: any;
  onEdit: (message: Message, content: string) => void;
  onRegenerate: (message: Message) => void;
}> = ({ message, thread, onEdit, onRegenerate }) => {
  const isHuman = message.type === 'human';
  const meta = thread.getMessagesMetadata?.(message);
  
  return (
    <div className={`flex gap-4 ${isHuman ? 'justify-end' : 'justify-start'} group`}>
      {!isHuman && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
          <Bot className="w-5 h-5 text-blue-600" />
        </div>
      )}
      
      <div className={`max-w-4xl ${isHuman ? 'bg-blue-500 text-white' : 'bg-white'} rounded-lg p-4 shadow-sm`}>
        <MessageContent content={message.content as string} />
        
        <div className="flex items-center justify-between mt-2">
          <div className="flex items-center gap-2">
            {isHuman && (
              <EditMessage
                message={message}
                onEdit={(content) => onEdit(message, content)}
              />
            )}
            
            {!isHuman && (
              <button
                type="button"
                onClick={() => onRegenerate(message)}
                className="p-1 rounded hover:bg-gray-100 opacity-0 group-hover:opacity-100 transition-opacity"
                title="Regenerate response"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            )}
          </div>
          
          <BranchSwitcher
            branch={meta?.branch}
            branchOptions={meta?.branchOptions}
            onSelect={(branch) => thread.setBranch?.(branch)}
          />
        </div>
      </div>
      
      {isHuman && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center">
          <User className="w-5 h-5 text-gray-600" />
        </div>
      )}
    </div>
  );
};

const ChatInput: React.FC<{
  onSubmit: (message: string) => void;
  isLoading: boolean;
  onStop: () => void;
}> = ({ onSubmit, isLoading, onStop }) => {
  const [message, setMessage] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = () => {
    if (message.trim() && !isLoading) {
      onSubmit(message.trim());
      setMessage('');
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const adjustTextareaHeight = () => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
    }
  };

  useEffect(() => {
    adjustTextareaHeight();
  }, [message]);

  return (
    <div className="border-t bg-white p-4">
      <div className="max-w-4xl mx-auto">
        <div className="relative flex items-end gap-3 p-3 border rounded-lg bg-gray-50">
          <textarea
            ref={textareaRef}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask me anything..."
            className="flex-1 resize-none bg-transparent border-none outline-none min-h-[24px] max-h-[200px] placeholder-gray-500"
            rows={1}
          />
          
          {isLoading ? (
            <button
              type="button"
              onClick={onStop}
              className="flex-shrink-0 p-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
              title="Stop generation"
            >
              <Square className="w-4 h-4" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!message.trim()}
              className="flex-shrink-0 p-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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

const Sidebar: React.FC<{
  threadId: string | null;
  onNewThread: () => void;
}> = ({ threadId, onNewThread }) => {
  return (
    <div className="w-64 bg-gray-100 border-r flex flex-col">
      <div className="p-4 border-b">
        <button
          onClick={onNewThread}
          className="w-full flex items-center gap-2 p-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Chat
        </button>
      </div>
      
      <div className="flex-1 p-4">
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm text-gray-600 mb-2">
            <MessageSquare className="w-4 h-4" />
            Recent Conversations
          </div>
          
          {threadId && (
            <div className="p-2 bg-white rounded border text-sm">
              Thread: {threadId.slice(0, 8)}...
            </div>
          )}
        </div>
      </div>
      
      <div className="p-4 border-t">
        <button className="w-full flex items-center gap-2 p-2 text-gray-600 hover:bg-gray-200 rounded">
          <Settings className="w-4 h-4" />
          Settings
        </button>
      </div>
    </div>
  );
};

const InterruptDialog: React.FC<{
  interrupt: any;
  onResume: () => void;
  onCancel: () => void;
}> = ({ interrupt, onResume, onCancel }) => {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
        <h3 className="text-lg font-semibold mb-4">Agent Needs Your Input</h3>
        <p className="text-gray-600 mb-6">{interrupt?.value || 'The agent is waiting for your confirmation.'}</p>
        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 border rounded-lg hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={onResume}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
          >
            Continue
          </button>
        </div>
      </div>
    </div>
  );
};

// Main Chat Component
const LangGraphChat: React.FC = () => {
  const [threadId, setThreadId] = useSearchParam('threadId');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const thread = useStream<AgentState>({
    apiUrl: "http://localhost:2024", // Your LangGraph server URL
    assistantId: "agent", // This should match your agent ID in the server
    threadId: threadId,
    onThreadId: setThreadId,
    messagesKey: "messages",
    reconnectOnMount: true,
    
    // Event handlers for monitoring your agent
    onCreated: (run) => {
      console.log('Run created:', run);
      if (typeof window !== 'undefined') {
        window.sessionStorage.setItem(`resume:${run.thread_id}`, run.run_id);
      }
    },
    onFinish: (result, run) => {
      console.log('Run finished:', result, run);
      if (run?.thread_id && typeof window !== 'undefined') {
        window.sessionStorage.removeItem(`resume:${run.thread_id}`);
      }
    },
    onError: (error) => {
      console.error('Stream error:', error);
    },
    onUpdateEvent: (event) => {
      console.log('Update event:', event);
    },
    onCustomEvent: (event) => {
      console.log('Custom event:', event);
    }
  });

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [thread.messages]);

  const handleSubmit = (message: string) => {
    const newMessage = { type: 'human' as const, content: message };
    
    thread.submit(
      { messages: [newMessage] },
      {
        streamResumable: true,
        optimisticValues: (prev) => ({
          ...prev,
          messages: [...(prev.messages || []), newMessage]
        })
      }
    );
  };

  const handleEdit = (message: Message, content: string) => {
    const meta = thread.getMessagesMetadata?.(message);
    const parentCheckpoint = meta?.firstSeenState?.parent_checkpoint;
    
    thread.submit(
      { messages: [{ type: 'human', content }] },
      { checkpoint: parentCheckpoint }
    );
  };

  const handleRegenerate = (message: Message) => {
    const meta = thread.getMessagesMetadata?.(message);
    const parentCheckpoint = meta?.firstSeenState?.parent_checkpoint;
    
    thread.submit(undefined, { checkpoint: parentCheckpoint });
  };

  const handleNewThread = () => {
    setThreadId(null);
  };

  const handleResumeInterrupt = () => {
    thread.submit(undefined, { command: { resume: true } });
  };

  const handleCancelInterrupt = () => {
    thread.stop();
  };

  // Extract loading messages from thread values
  const loadingMessages: LoadingMessage[] = thread.values?.loading_messages || [];

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar threadId={threadId} onNewThread={handleNewThread} />
      
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="bg-white border-b p-4">
          <div className="max-w-4xl mx-auto">
            <h1 className="text-xl font-semibold text-gray-800">LangGraph Assistant</h1>
            {thread.values?.detected_language && (
              <p className="text-sm text-gray-600">
                Language: {thread.values.detected_language}
              </p>
            )}
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4">
          <div className="max-w-4xl mx-auto space-y-6">
            {/* Loading Messages */}
            {thread.isLoading && <LoadingIndicator messages={loadingMessages} />}
            
            {/* Chat Messages */}
            {thread.messages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                thread={thread}
                onEdit={handleEdit}
                onRegenerate={handleRegenerate}
              />
            ))}
            
            {/* Empty State */}
            {thread.messages.length === 0 && !thread.isLoading && (
              <div className="text-center py-12">
                <Bot className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h2 className="text-xl font-semibold text-gray-600 mb-2">
                  How can I help you today?
                </h2>
                <p className="text-gray-500">
                  Ask me anything and I'll search for the best information to help you.
                </p>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input */}
        <ChatInput
          onSubmit={handleSubmit}
          isLoading={thread.isLoading}
          onStop={thread.stop}
        />
      </div>

      {/* Interrupt Dialog */}
      {thread.interrupt && (
        <InterruptDialog
          interrupt={thread.interrupt}
          onResume={handleResumeInterrupt}
          onCancel={handleCancelInterrupt}
        />
      )}
    </div>
  );
};

export default LangGraphChat;
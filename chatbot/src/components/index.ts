// Main Chat Application
export { ChatApp } from './ChatApp';

// UI Components
export { LoadingIndicator } from './LoadingIndicator';
export { MessageContent } from './MessageContent';
export { BranchSwitcher } from './BranchSwitcher';
export { EditMessage } from './EditMessage';
export { MessageBubble } from './MessageBubble';
export { ChatInput } from './ChatInput';
export { Sidebar } from './Sidebar';
export { InterruptDialog } from './InterruptDialog';

// Component Types
export interface Message {
  id?: string;
  content: string;
  type: 'human' | 'ai';
}

export interface LoadingMessage {
  message: string;
  level: 'info' | 'success' | 'warning' | 'error' | 'debug';
  timestamp: string;
}

export interface Thread {
  id: string;
  title: string;
  lastMessage?: string;
}

export interface MessageMeta {
  branch?: string;
  branchOptions?: string[];
}
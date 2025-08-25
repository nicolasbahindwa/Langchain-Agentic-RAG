import React from 'react';
import { Plus, MessageSquare, Settings } from 'lucide-react';

interface Thread {
  id: string;
  title: string;
  lastMessage?: string;
}

interface SidebarProps {
  threadId?: string | null;
  onNewThread?: () => void;
  recentThreads?: Thread[];
}

export const Sidebar: React.FC<SidebarProps> = ({ 
  threadId, 
  onNewThread, 
  recentThreads = [] 
}) => {
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
      
      <div className="flex-1 p-4 overflow-y-auto">
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm text-gray-600 mb-2">
            <MessageSquare className="w-4 h-4" />
            Recent Conversations
          </div>
          
          {threadId && (
            <div className="p-2 bg-white rounded border text-sm">
              <div className="font-medium">Current Thread</div>
              <div className="text-gray-500 text-xs">{threadId.slice(0, 8)}...</div>
            </div>
          )}
          
          {recentThreads.map((thread) => (
            <div key={thread.id} className="p-2 bg-white rounded border text-sm hover:bg-gray-50 cursor-pointer">
              <div className="font-medium truncate">{thread.title}</div>
              {thread.lastMessage && (
                <div className="text-gray-500 text-xs truncate mt-1">{thread.lastMessage}</div>
              )}
            </div>
          ))}
          
          {recentThreads.length === 0 && !threadId && (
            <div className="text-center text-gray-500 text-sm py-4">
              No conversations yet
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
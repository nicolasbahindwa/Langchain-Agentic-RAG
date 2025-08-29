import React from 'react';
import { RefreshCw, User, Bot } from 'lucide-react';
import { MessageContent } from './MessageContent';
import { BranchSwitcher } from './BranchSwitcher';
import { EditMessage } from './EditMessage';

interface Message {
  id?: string;
  content: string;
  type: 'human' | 'ai';
}

interface MessageMeta {
  branch?: string;
  branchOptions?: string[];
}

interface MessageBubbleProps {
  message: Message;
  messageMeta?: MessageMeta;
  onEdit?: (message: Message, content: string) => void;
  onRegenerate?: (message: Message) => void;
  onBranchSelect?: (branch: string) => void;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ 
  message, 
  messageMeta,
  onEdit, 
  onRegenerate,
  onBranchSelect
}) => {
  const isHuman = message.type === 'human';
  
  if (isHuman) {
    // Human messages: right-aligned, from right to center
    return (
      <div className="flex justify-end group">
        <div className="flex gap-3 items-start max-w-2xl">
          <div className="bg-blue-500 text-white rounded-2xl px-4 py-3 shadow-sm">
            <EditMessage
              message={message}
              onEdit={(content: string) => onEdit?.(message, content)}
              isHuman={true}
            >
              <MessageContent content={message.content} isHuman={true} />
            </EditMessage>
            
            <div className="flex items-center justify-between mt-2">
              <div className="flex items-center gap-2">
                {/* Edit button is now inside EditMessage component */}
              </div>
              
              <BranchSwitcher
                branch={messageMeta?.branch}
                branchOptions={messageMeta?.branchOptions}
                onSelect={onBranchSelect || (() => {})}
              />
            </div>
          </div>
          
          <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center">
            <User className="w-4 h-4 text-white" />
          </div>
        </div>
      </div>
    );
  }
  
  // AI messages: left-aligned, from left to center
  return (
    <div className="flex justify-start group">
      <div className="flex gap-3 items-start max-w-3xl">
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
          <Bot className="w-5 h-5 text-blue-600" />
        </div>
        
        <div className="bg-white rounded-2xl px-4 py-3 shadow-sm border border-gray-100">
          <MessageContent content={message.content} isHuman={false} />
          
          <div className="flex items-center justify-between mt-2">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => onRegenerate?.(message)}
                className="p-1 rounded hover:bg-gray-100 opacity-0 group-hover:opacity-100 transition-opacity"
                title="Regenerate response"
              >
                <RefreshCw className="w-4 h-4 text-gray-600" />
              </button>
            </div>
            
            <BranchSwitcher
              branch={messageMeta?.branch}
              branchOptions={messageMeta?.branchOptions}
              onSelect={onBranchSelect || (() => {})}
            />
          </div>
        </div>
      </div>
    </div>
  );
};
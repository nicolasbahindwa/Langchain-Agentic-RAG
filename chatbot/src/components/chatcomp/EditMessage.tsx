import React, { useState } from 'react';
import { Edit3 } from 'lucide-react';

interface Message {
  id?: string;
  content: string;
  type: 'human' | 'ai';
}

interface EditMessageProps {
  message: Message;
  onEdit?: (content: string) => void;
  isHuman?: boolean;
  children?: React.ReactNode; // This will be the MessageContent component
}

export const EditMessage: React.FC<EditMessageProps> = ({ message, onEdit, isHuman = false, children }) => {
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState(message.content);

  const handleSubmit = () => {
    if (onEdit) onEdit(editContent);
    setEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && e.ctrlKey) {
      handleSubmit();
    }
    if (e.key === 'Escape') {
      setEditing(false);
      setEditContent(message.content); // Reset content on cancel
    }
  };

  if (editing) {
    return (
      <div className="space-y-3">
        <textarea
          value={editContent}
          onChange={(e) => setEditContent(e.target.value)}
          onKeyDown={handleKeyDown}
          className={`w-full p-3 border rounded-lg resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent min-h-[120px] ${
            isHuman ? 'bg-white text-gray-900' : 'bg-gray-50'
          }`}
          autoFocus
          placeholder="Edit your message..."
        />
        
        <div className={`text-xs ${isHuman ? 'text-blue-100' : 'text-gray-500'} mb-3`}>
          💡 Editing this message will create a new conversation branch. You can switch between branches using the arrow navigation buttons.
        </div>
        
        <div className="flex gap-2 justify-end">
          <button
            type="button"
            onClick={() => {
              setEditing(false);
              setEditContent(message.content);
            }}
            className={`px-3 py-1 border rounded text-sm transition-colors ${
              isHuman 
                ? 'border-blue-200 text-blue-100 hover:bg-blue-400 hover:bg-opacity-20' 
                : 'border-gray-300 text-gray-600 hover:bg-gray-50'
            }`}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            className="px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm transition-colors"
          >
            Save & Create Branch
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="relative group">
      {children}
      <button
        type="button"
        onClick={() => setEditing(true)}
        className={`absolute -bottom-10 left-0 p-1 rounded transition-opacity opacity-0 group-hover:opacity-100 ${
          isHuman 
            ? 'hover:bg-blue-400 hover:bg-opacity-30' 
            : 'hover:bg-gray-100'
        }`}
        title="Edit message"
      >
        <Edit3 className={`w-4 h-4 ${isHuman ? 'text-blue-100' : 'text-gray-600'}`} />
      </button>
    </div>
  );
};
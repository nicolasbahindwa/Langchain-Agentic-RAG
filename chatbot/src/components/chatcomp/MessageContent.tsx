import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';

interface MessageContentProps {
  content: string;
  isHuman?: boolean;
}

export const MessageContent: React.FC<MessageContentProps> = ({ content, isHuman = false }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy text:', err);
    }
  };

  return (
    <div className="relative group">
      <div className="prose prose-sm max-w-none">
        <div className="whitespace-pre-wrap">{content}</div>
      </div>
      <button
        onClick={handleCopy}
        className={`absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded ${
          isHuman 
            ? 'hover:bg-blue-400 hover:bg-opacity-30' 
            : 'hover:bg-gray-100'
        }`}
        title="Copy message"
      >
        {copied ? (
          <Check className={`w-4 h-4 ${isHuman ? 'text-blue-100' : 'text-green-500'}`} />
        ) : (
          <Copy className={`w-4 h-4 ${isHuman ? 'text-blue-100' : 'text-gray-600'}`} />
        )}
      </button>
    </div>
  );
};
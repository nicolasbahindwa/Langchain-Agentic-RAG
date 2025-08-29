import React from 'react';
import { Check, AlertCircle, Loader2 } from 'lucide-react';

interface LoadingMessage {
  message: string;
  level: 'info' | 'success' | 'warning' | 'error' | 'debug';
  timestamp: string;
}

interface LoadingIndicatorProps {
  messages: LoadingMessage[];
}

export const LoadingIndicator: React.FC<LoadingIndicatorProps> = ({ messages }) => {
  if (!messages || messages.length === 0) return null;
  
  const latestMessage = messages[messages.length - 1];

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
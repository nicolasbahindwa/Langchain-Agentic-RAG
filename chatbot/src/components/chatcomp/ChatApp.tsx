import React from 'react';
import { Bot } from 'lucide-react';

// Import all components
import { LoadingIndicator } from './LoadingIndicator';
import { MessageBubble } from './MessageBubble';
import { ChatInput } from './ChatInput';
import { Sidebar } from './Sidebar';
import { InterruptDialog } from './InterruptDialog';

// Sample data for UI design demonstration
const sampleMessages = [
  {
    id: '1',
    content: "Hello! I need help with analyzing some data from our recent marketing campaign. Can you help me understand the key metrics?",
    type: 'human' as const,
  },
  {
    id: '2',
    content: "I'd be happy to help you analyze your marketing campaign data! I can assist you with:\n\n• **Performance Metrics** - CTR, conversion rates, ROAS\n• **Audience Analysis** - Demographics, engagement patterns\n• **Channel Comparison** - Which platforms performed best\n• **Trend Identification** - Growth patterns and opportunities\n\nWhat specific aspects would you like to focus on first? If you have data files, feel free to upload them.",
    type: 'ai' as const,
  },
  {
    id: '3',
    content: "That's perfect! I'm particularly interested in the conversion rates across different channels. Let me upload the campaign data.",
    type: 'human' as const,
  },
];

const sampleLoadingMessages = [
  {
    message: "Analyzing uploaded data...",
    level: 'info' as const,
    timestamp: new Date().toISOString()
  }
];

const sampleThreads = [
  {
    id: 'thread-1',
    title: 'Marketing Campaign Analysis',
    lastMessage: 'Thanks for the detailed breakdown!'
  },
  {
    id: 'thread-2', 
    title: 'Sales Data Review',
    lastMessage: 'Can you show me Q3 trends?'
  },
  {
    id: 'thread-3',
    title: 'Customer Segmentation',
    lastMessage: 'The demographic analysis was very helpful.'
  }
];

// Main Chat Application Component (UI Design Only)
export const ChatApp: React.FC = () => {
  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar 
        threadId="current-thread-123"
        recentThreads={sampleThreads}
      />
      
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="bg-white border-b p-4">
          <div className="max-w-4xl mx-auto">
            <h1 className="text-xl font-semibold text-gray-800">LangGraph Assistant</h1>
            <p className="text-sm text-gray-600">
              Language: English • Thread: current-thread-123
            </p>
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-4">
          <div className="max-w-4xl mx-auto space-y-6">
            {/* Sample Loading Indicator */}
            <LoadingIndicator messages={sampleLoadingMessages} />
            
            {/* Sample Chat Messages */}
            {sampleMessages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                messageMeta={{
                  branch: 'main',
                  branchOptions: ['main', 'alternative', 'detailed']
                }}
              />
            ))}
            
            {/* Typing Indicator for AI Response */}
            <div className="flex justify-start">
              <div className="flex gap-3 items-start max-w-3xl">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                  <Bot className="w-5 h-5 text-blue-600" />
                </div>
                <div className="bg-white rounded-2xl px-4 py-3 shadow-sm border border-gray-100">
                  <div className="flex items-center gap-2 text-gray-500">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    </div>
                    <span className="text-sm">Assistant is typing...</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Input Area */}
        <ChatInput isLoading={true} />
      </div>

      {/* Sample Interrupt Dialog (hidden by default) */}
      <InterruptDialog
        interrupt={{ value: "I found multiple data formats in your file. Which format should I prioritize for the analysis?" }}
        isOpen={false}
      />
    </div>
  );
};
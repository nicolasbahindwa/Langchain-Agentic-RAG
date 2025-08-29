import React from 'react';

interface InterruptData {
  value?: string;
  type?: string;
}

interface InterruptDialogProps {
  interrupt?: InterruptData;
  onResume?: () => void;
  onCancel?: () => void;
  isOpen: boolean;
}

export const InterruptDialog: React.FC<InterruptDialogProps> = ({ 
  interrupt, 
  onResume, 
  onCancel,
  isOpen
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
        <h3 className="text-lg font-semibold mb-4">Agent Needs Your Input</h3>
        <p className="text-gray-600 mb-6">
          {interrupt?.value || 'The agent is waiting for your confirmation.'}
        </p>
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
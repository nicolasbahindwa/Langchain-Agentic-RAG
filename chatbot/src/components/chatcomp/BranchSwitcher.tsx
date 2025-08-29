import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface BranchSwitcherProps {
  branch?: string;
  branchOptions?: string[];
  onSelect: (branch: string) => void;
}

export const BranchSwitcher: React.FC<BranchSwitcherProps> = ({ 
  branch, 
  branchOptions, 
  onSelect 
}) => {
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
        className="p-1 rounded hover:bg-white-100 text-white disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <ChevronLeft className="w-3 h-3" />
      </button>
      <span className="px-2 text-white">
        {index + 1} / {branchOptions.length}
      </span>
      <button
        type="button"
        onClick={() => {
          const nextBranch = branchOptions[index + 1];
          if (nextBranch) onSelect(nextBranch);
        }}
        disabled={index === branchOptions.length - 1}
        className="p-1 rounded hover:bg-gray-100 text-white disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <ChevronRight className="w-3 h-3" />
      </button>
    </div>
  );
};
import React from "react";

// Utility function for formatting markdown into HTML
export const formatMarkdown = (text: string): string => {
  return text
    // Headers
    .replace(/^###### (.*$)/gim, '<h6 class="text-sm font-medium mt-4 mb-2 text-gray-700">$1</h6>')
    .replace(/^##### (.*$)/gim, '<h5 class="text-base font-medium mt-4 mb-2 text-gray-700">$1</h5>')
    .replace(/^#### (.*$)/gim, '<h4 class="text-base font-semibold mt-5 mb-2 text-gray-800">$1</h4>')
    .replace(/^### (.*$)/gim, '<h3 class="text-lg font-semibold mt-6 mb-3 text-gray-800">$1</h3>')
    .replace(/^## (.*$)/gim, '<h2 class="text-xl font-semibold mt-6 mb-3 text-gray-800">$1</h2>')
    .replace(/^# (.*$)/gim, '<h1 class="text-2xl font-bold mt-6 mb-4 text-gray-900">$1</h1>')
    // Bold / italic
    .replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold text-gray-900">$1</strong>')
    .replace(/\*(.*?)\*/g, '<em class="italic text-gray-700">$1</em>')
    // Code blocks
    .replace(/```([\s\S]*?)```/g, '<pre class="bg-gray-50 border border-gray-200 p-4 rounded-lg mt-3 mb-3 overflow-x-auto text-sm"><code class="text-gray-800">$1</code></pre>')
    // Inline code
    .replace(/`([^`]*)`/g, '<code class="bg-gray-100 px-2 py-1 rounded text-sm font-mono text-gray-800">$1</code>')
    // Citations
    .replace(/\[(\d+)\]/g, '<sup class="text-blue-600 font-medium text-xs">[$1]</sup>')
    // Bullet points
    .replace(/^\* (.*$)/gim, '<li class="ml-4 mb-1 text-gray-700">$1</li>')
    .replace(/(<li.*<\/li>)/s, '<ul class="list-disc list-outside my-3 space-y-1">$1</ul>')
    // Numbered lists
    .replace(/^\d+\. (.*$)/gim, '<li class="ml-4 mb-1 text-gray-700">$1</li>')
    // Markdown images
    .replace(/!\[([^\]]*)\]\((https?:\/\/[^\s)]+)\)/g, '<img src="$2" alt="$1" class="rounded-lg my-3 max-w-full" />')
    // Markdown links
    .replace(
      /(https?:\/\/[^\s<>"')]+)/g,
      '<a href="$1" target="_blank" rel="noopener noreferrer" class="text-blue-600 underline">$1</a>'
    )
    // Paragraphs and line breaks
    .replace(/\n\n/g, '</p><p class="mb-3 text-gray-700 leading-relaxed">')
    .replace(/\n/g, '<br>');
};

// React component
export const MarkdownRenderer: React.FC<{ content: string }> = ({ content }) => {
  const htmlContent = formatMarkdown(content);

  return (
    <div
      className="prose prose-sm max-w-none text-gray-700"
      dangerouslySetInnerHTML={{
        __html: `<div class="leading-relaxed">${htmlContent}</div>`
      }}
    />
  );
};

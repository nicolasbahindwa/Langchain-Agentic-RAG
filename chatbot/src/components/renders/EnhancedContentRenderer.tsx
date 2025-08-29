// components/EnhancedContentRenderer.tsx
import React from 'react';
import { parseContent } from './parsers';
import ChartRenderer from './ChartRenderer';
import TableRenderer  from './TableRenderer';
import { MarkdownRenderer } from './MarkdownRenderer';

interface EnhancedContentRendererProps {
  content: string;
  userQuery?: string; // Add user query for context-aware parsing
}

export const EnhancedContentRenderer: React.FC<EnhancedContentRendererProps> = ({ content, userQuery = '' }) => {
  const parsedContent = parseContent(content, userQuery);

  switch (parsedContent.type) {
    case 'graph':
      return <ChartRenderer graphData={parsedContent.content} />;
      
    case 'table':
      return <TableRenderer tableData={parsedContent.content} />;
      
    case 'mixed':
      // Handle mixed content by splitting and rendering each part
      const sections = parsedContent.content.split(/\n(?=GRAPH:|TABLE:|\|)/);
      return (
        <div>
          {sections.map((section: string, index: number) => {
            const sectionParsed = parseContent(section.trim());
            if (sectionParsed.type === 'graph') {
              return <ChartRenderer key={index} graphData={sectionParsed.content} />;
            } else if (sectionParsed.type === 'table') {
              return <TableRenderer key={index} tableData={sectionParsed.content} />;
            } else {
              return <MarkdownRenderer key={index} content={section} />;
            }
          })}
        </div>
      );
      
    case 'text':
    default:
      return <MarkdownRenderer content={content} />;
  }
};
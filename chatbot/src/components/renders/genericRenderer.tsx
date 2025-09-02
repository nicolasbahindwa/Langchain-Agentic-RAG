import React, { useState, useMemo, useEffect } from 'react';
import {
  LineChart,
  BarChart,
  AreaChart,
  PieChart,
  ScatterChart,
  ComposedChart,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Line,
  Bar,
  Area,
  Pie,
  Cell,
  Scatter,
  Radar
} from 'recharts';
import { TrendingUp, Copy, RotateCcw } from 'lucide-react';

// Types
interface SeriesData {
  name: string;
  data: Array<{ x: string | number; y: number; [key: string]: any }>;
}

interface GraphData {
  type: 'bar' | 'line' | 'pie' | 'area' | 'scatter' | 'composed' | 'radar';
  title: string;
  data?: Array<{ [key: string]: any }>; // Old format
  series?: SeriesData[]; // New format
  xLabel?: string;
  yLabel?: string;
  xDataKey?: string;
  yDataKey?: string;
  isMultiSeries?: boolean;
  seriesKeys?: string[];
}

interface TableData {
  headers: string[];
  rows: string[][];
  title?: string;
}

// Constants
const CHART_COLORS = [
  '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
  '#ec4899', '#06b6d4', '#f97316', '#84cc16', '#6366f1'
];

// Utility Functions
const parseNumber = (value: any): number => {
  if (typeof value === 'number') return value;
  if (typeof value === 'string') {
    const cleaned = value.replace(/[$,%]/g, '');
    const parsed = parseFloat(cleaned);
    return isNaN(parsed) ? 0 : parsed;
  }
  return 0;
};

const formatLargeNumber = (num: number): string => {
  if (num >= 1000000000) return `${(num / 1000000000).toFixed(1)}B`;
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return num.toString();
};

// Enhanced Parser Functions
// Streaming-safe parser that only processes complete blocks
const parseContent = (content: string) => {
  console.log('=== STREAMING-SAFE PARSE START ===');
  
  // Handle undefined or null content
  if (!content || typeof content !== 'string') {
    return { graphs: [], tables: [], textContent: content || '' };
  }
  
  const graphs: GraphData[] = [];
  const tables: TableData[] = [];
  let cleanContent = content;
  
  // STEP 1: Only process COMPLETE table blocks
  const processCompleteTableBlocks = () => {
    let currentPos = 0;
    while (true) {
      const tableStart = cleanContent.indexOf('<TABLE_DATA>', currentPos);
      if (tableStart === -1) break;
      
      const tableEnd = cleanContent.indexOf('</TABLE_DATA>', tableStart);
      if (tableEnd === -1) {
        console.log('TABLE_DATA block incomplete - skipping until stream completes');
        break; // Incomplete block - don't process yet
      }
      
      // We have a complete block
      const fullTableBlock = cleanContent.substring(tableStart, tableEnd + '</TABLE_DATA>'.length);
      console.log('Processing complete TABLE_DATA block');
      
      // Extract JSON
      const jsonStart = cleanContent.indexOf('{', tableStart);
      const jsonEnd = cleanContent.lastIndexOf('}', tableEnd);
      
      if (jsonStart === -1 || jsonEnd === -1 || jsonStart >= tableEnd) {
        console.error('Invalid JSON structure in table block');
        // Remove the malformed block
        cleanContent = cleanContent.replace(fullTableBlock, '<!-- MALFORMED_TABLE -->');
        currentPos = 0; // Restart search
        continue;
      }
      
      const jsonContent = cleanContent.substring(jsonStart, jsonEnd + 1);
      
      try {
        const jsonData = JSON.parse(jsonContent);
        
        if (jsonData.columns && jsonData.rows) {
          const tableData: TableData = {
            headers: jsonData.columns,
            rows: jsonData.rows,
            title: jsonData.title
          };
          tables.push(tableData);
          
          // Replace with placeholder
          const placeholder = `<!-- TABLE_${tables.length - 1} -->`;
          cleanContent = cleanContent.replace(fullTableBlock, placeholder);
          console.log('Successfully processed table, replaced with:', placeholder);
          
          // Restart search from beginning
          currentPos = 0;
        } else {
          console.error('Table JSON missing required fields');
          currentPos = tableEnd + '</TABLE_DATA>'.length;
        }
      } catch (e) {
        console.error('Failed to parse table JSON:', e);
        // Remove the malformed block
        cleanContent = cleanContent.replace(fullTableBlock, '<!-- INVALID_TABLE_JSON -->');
        currentPos = 0;
      }
    }
  };

// NEW: Process graph data supporting both old and new formats
const processGraphData = (jsonData: any): GraphData | null => {
  const { type, title, xLabel, yLabel, xDataKey = 'x', yDataKey = 'y' } = jsonData;
  
  // NEW FORMAT: Handle series array
  if (jsonData.series && Array.isArray(jsonData.series)) {
    // Convert new series format to Recharts format
    const { processedData, seriesKeys } = convertSeriesToRecharts(jsonData.series, xDataKey, yDataKey);
    
    return {
      type,
      title,
      data: processedData,
      xLabel,
      yLabel,
      xDataKey,
      yDataKey,
      isMultiSeries: true,
      seriesKeys
    };
  }
  
  // OLD FORMAT: Handle direct data array
  if (jsonData.data && Array.isArray(jsonData.data)) {
    // Apply the existing logic for backward compatibility
    const { processedData, chartType, isMultiSeries, seriesKeys } = processChartDataLegacy(jsonData);
    
    return {
      type: chartType,
      title,
      data: processedData,
      xLabel,
      yLabel,
      xDataKey,
      yDataKey,
      isMultiSeries,
      seriesKeys
    };
  }
  
  console.warn('Invalid graph data format:', jsonData);
  return null;
};


const processCompleteGraphBlocks = () => {
    let currentPos = 0;
    while (true) {
      const graphStart = cleanContent.indexOf('<GRAPH_DATA>', currentPos);
      if (graphStart === -1) break;
      
      const graphEnd = cleanContent.indexOf('</GRAPH_DATA>', graphStart);
      if (graphEnd === -1) {
        console.log('GRAPH_DATA block incomplete - skipping until stream completes');
        break; // Incomplete block - don't process yet
      }
      
      // We have a complete block
      const fullGraphBlock = cleanContent.substring(graphStart, graphEnd + '</GRAPH_DATA>'.length);
      console.log('Processing complete GRAPH_DATA block');
      
      // Extract JSON
      const jsonStart = cleanContent.indexOf('{', graphStart);
      const jsonEnd = cleanContent.lastIndexOf('}', graphEnd);
      
      if (jsonStart === -1 || jsonEnd === -1 || jsonStart >= graphEnd) {
        console.error('Invalid JSON structure in graph block');
        // Remove the malformed block
        cleanContent = cleanContent.replace(fullGraphBlock, '<!-- MALFORMED_GRAPH -->');
        currentPos = 0;
        continue;
      }
      
      const jsonContent = cleanContent.substring(jsonStart, jsonEnd + 1);
      
      try {
        const jsonData = JSON.parse(jsonContent);
        
        if (jsonData.type && jsonData.title) {
          const processedGraph = processGraphData(jsonData);
          if (processedGraph) {
            graphs.push(processedGraph);
            
            // Replace with placeholder
            const placeholder = `<!-- GRAPH_${graphs.length - 1} -->`;
            cleanContent = cleanContent.replace(fullGraphBlock, placeholder);
            console.log('Successfully processed graph, replaced with:', placeholder);
            
            // Restart search from beginning
            currentPos = 0;
          } else {
            console.error('processGraphData returned null');
            currentPos = graphEnd + '</GRAPH_DATA>'.length;
          }
        } else {
          console.error('Graph JSON missing required fields');
          currentPos = graphEnd + '</GRAPH_DATA>'.length;
        }
      } catch (e) {
        console.error('Failed to parse graph JSON:', e);
        // Remove the malformed block
        cleanContent = cleanContent.replace(fullGraphBlock, '<!-- INVALID_GRAPH_JSON -->');
        currentPos = 0;
      }
    }
  };

  // Process complete blocks only
  processCompleteTableBlocks();
  processCompleteGraphBlocks();
  
  console.log('=== STREAMING-SAFE PARSE END ===');
  console.log('Successfully processed - Tables:', tables.length, 'Graphs:', graphs.length);
  
  return { graphs, tables, textContent: cleanContent.trim() };
};



// NEW: Convert new series format to Recharts format
const convertSeriesToRecharts = (series: SeriesData[], xDataKey: string, yDataKey: string) => {
  if (!series || series.length === 0) {
    return { processedData: [], seriesKeys: [] };
  }
  
  // Get all unique x values across all series
  const allXValues = new Set<string>();
  series.forEach(s => {
    if (s.data && Array.isArray(s.data)) {
      s.data.forEach(point => {
        allXValues.add(String(point[xDataKey] || point.x || ''));
      });
    }
  });
  
  const sortedXValues = Array.from(allXValues).sort();
  
  // Build the data structure that Recharts expects
  const processedData = sortedXValues.map(xValue => {
    const dataPoint: any = { [xDataKey]: xValue };
    
    // For each series, find the corresponding y value for this x
    series.forEach(s => {
      if (s.data && Array.isArray(s.data)) {
        const point = s.data.find(p => String(p[xDataKey] || p.x || '') === xValue);
        dataPoint[s.name] = point ? parseNumber(point[yDataKey] || point.y) : null;
      }
    });
    
    return dataPoint;
  });
  
  const seriesKeys = series.map(s => s.name);
  
  return { processedData, seriesKeys };
};

// LEGACY: Keep the old logic for backward compatibility
const processChartDataLegacy = (jsonData: any) => {
  const { data, type: suggestedType, xDataKey = 'x', yDataKey = 'y' } = jsonData;
  
  if (!data || !Array.isArray(data) || data.length === 0) {
    return { processedData: data, chartType: suggestedType || 'bar' };
  }
  
  // Check for multi-series data (same x values with different y values)
  const xValues = data.map(item => item[xDataKey]);
  const uniqueXValues = [...new Set(xValues)];
  const hasDuplicateXValues = xValues.length !== uniqueXValues.length;
  
  // If we have duplicate x values, this is likely multi-series data that needs restructuring
  if (hasDuplicateXValues) {
    // Calculate how many series we have
    const seriesCount = Math.floor(data.length / uniqueXValues.length);
    
    // Group data by x value and create proper multi-series structure
    const groupedData = {};
    
    // Detect series names based on title and context
    const title = jsonData.title?.toLowerCase() || '';
    let seriesNames = [];
    
    // Enhanced detection for common comparison patterns
    if (title.includes('us') && title.includes('eu')) {
      seriesNames = ['US', 'EU'];
    } else if (title.includes('united states') && title.includes('european')) {
      seriesNames = ['United States', 'European Union'];
    } else if (title.includes('america') && title.includes('europe')) {
      seriesNames = ['America', 'Europe'];
    } else if (title.includes('facebook') && title.includes('instagram') && title.includes('tiktok')) {
      seriesNames = ['Facebook', 'Instagram', 'TikTok'];
    } else if (title.includes('vs') || title.includes('comparison')) {
      // Generic comparison - try to extract names or use generic labels
      const parts = title.split(/vs|comparison|compare/);
      if (parts.length >= 2) {
        seriesNames = parts.map(part => part.trim().replace(/[^\w\s]/g, '')).filter(s => s.length > 0);
      }
      if (seriesNames.length < seriesCount) {
        seriesNames = Array.from({length: seriesCount}, (_, i) => `Series ${i + 1}`);
      }
    } else {
      // Default series names
      seriesNames = Array.from({length: seriesCount}, (_, i) => `Series ${i + 1}`);
    }
    
    // Ensure we have enough series names
    while (seriesNames.length < seriesCount) {
      seriesNames.push(`Series ${seriesNames.length + 1}`);
    }
    
    // Process data into grouped format
    uniqueXValues.forEach((xVal, xIndex) => {
      groupedData[xVal] = { [xDataKey]: xVal };
      
      // For each series, find the corresponding data point
      for (let seriesIndex = 0; seriesIndex < seriesCount; seriesIndex++) {
        const dataIndex = seriesIndex * uniqueXValues.length + xIndex;
        if (dataIndex < data.length) {
          const seriesName = seriesNames[seriesIndex];
          groupedData[xVal][seriesName] = data[dataIndex][yDataKey];
        }
      }
    });
    
    return {
      processedData: Object.values(groupedData),
      chartType: 'line', // Multi-series data typically works best as line charts
      isMultiSeries: true,
      seriesKeys: seriesNames.slice(0, seriesCount)
    };
  }
  
  // Single series data - apply normal logic
  const samplePoint = data[0];
  const keys = Object.keys(samplePoint);
  const isTimeData = keys.some(key => 
    key.toLowerCase().includes('year') || 
    key.toLowerCase().includes('month') || 
    key.toLowerCase().includes('date') ||
    key.toLowerCase().includes('time')
  );
  
  // Check if data represents percentages or parts of a whole
  const yValues = data.map(item => parseNumber(item[yDataKey]));
  const totalSum = yValues.reduce((sum, val) => sum + val, 0);
  const isPercentageData = totalSum >= 95 && totalSum <= 105; // Approximately 100%
  
  // Check for comparison data
  const hasMultipleCategories = data.length > 1;
  
  // Decision logic
  let chartType = suggestedType || 'bar';
  if (isPercentageData && data.length <= 8) {
    chartType = 'pie';
  } else if (isTimeData && hasMultipleCategories) {
    chartType = 'line';
  } else if (hasMultipleCategories && data.length > 8) {
    chartType = 'bar';
  }
  
  return { processedData: data, chartType, isMultiSeries: false };
};

// Components
const Table = ({ headers, rows, className = '' }) => (
  <div className={`w-full my-6 ${className}`}>
    <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
      <table className="min-w-full divide-y divide-gray-200 bg-white">
        <thead className="bg-gradient-to-r from-gray-50 to-gray-100">
          <tr>
            {headers.map((header, i) => (
              <th 
                key={i} 
                className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-r border-gray-200 last:border-r-0"
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {rows.map((row, i) => (
            <tr 
              key={i} 
              className={`${i % 2 === 0 ? 'bg-white' : 'bg-gray-50'} hover:bg-blue-50 transition-colors duration-150`}
            >
              {row.map((cell, j) => (
                <td 
                  key={j} 
                  className="px-4 py-3 text-sm text-gray-900 border-r border-gray-200 last:border-r-0"
                >
                  <div className="font-medium">{cell}</div>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
);

const Chart = ({ graph }) => {
  const { type, data, xLabel, yLabel, xDataKey, yDataKey, title, isMultiSeries, seriesKeys } = graph;
  const commonProps = { 
    data, 
    margin: { top: 20, right: 30, left: 20, bottom: 50 } 
  };

  // Debug logging
  console.log('Chart render:', { type, title, isMultiSeries, seriesKeys, dataLength: data?.length });

  const renderChart = () => {
    switch (type) {
      case 'bar':
        if (isMultiSeries && seriesKeys) {
          return (
            <BarChart {...commonProps}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis 
                dataKey={xDataKey} 
                angle={data.length > 6 ? -45 : 0} 
                textAnchor={data.length > 6 ? "end" : "middle"}
                height={data.length > 6 ? 80 : 60}
                fontSize={12}
              />
              <YAxis tickFormatter={formatLargeNumber} fontSize={12} />
              <Tooltip 
                formatter={(value, name) => [formatLargeNumber(Number(value)), name]}
                labelStyle={{ color: '#374151' }}
                contentStyle={{ 
                  backgroundColor: 'rgba(255, 255, 255, 0.95)', 
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                }}
              />
              <Legend />
              {seriesKeys.map((key, index) => (
                <Bar 
                  key={key}
                  dataKey={key} 
                  fill={CHART_COLORS[index % CHART_COLORS.length]} 
                  radius={[2, 2, 0, 0]} 
                />
              ))}
            </BarChart>
          );
        }
        return (
          <BarChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis 
              dataKey={xDataKey} 
              angle={data.length > 6 ? -45 : 0} 
              textAnchor={data.length > 6 ? "end" : "middle"}
              height={data.length > 6 ? 80 : 60}
              fontSize={12}
            />
            <YAxis tickFormatter={formatLargeNumber} fontSize={12} />
            <Tooltip 
              formatter={(value) => [formatLargeNumber(Number(value)), yLabel || 'Value']}
              labelStyle={{ color: '#374151' }}
              contentStyle={{ 
                backgroundColor: 'rgba(255, 255, 255, 0.95)', 
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
              }}
            />
            <Bar dataKey={yDataKey} fill={CHART_COLORS[0]} radius={[4, 4, 0, 0]} />
          </BarChart>
        );
      
      case 'line':
        if (isMultiSeries && seriesKeys) {
          return (
            <LineChart {...commonProps}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey={xDataKey} fontSize={12} />
              <YAxis tickFormatter={formatLargeNumber} fontSize={12} />
              <Tooltip 
                formatter={(value, name) => [formatLargeNumber(Number(value)), name]}
                contentStyle={{ 
                  backgroundColor: 'rgba(255, 255, 255, 0.95)', 
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px'
                }}
              />
              <Legend />
              {seriesKeys.map((key, index) => (
                <Line 
                  key={key}
                  type="monotone" 
                  dataKey={key} 
                  stroke={CHART_COLORS[index % CHART_COLORS.length]} 
                  strokeWidth={3} 
                  dot={{ r: 5 }}
                  activeDot={{ r: 7 }}
                />
              ))}
            </LineChart>
          );
        }
        return (
          <LineChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey={xDataKey} fontSize={12} />
            <YAxis tickFormatter={formatLargeNumber} fontSize={12} />
            <Tooltip 
              formatter={(value) => [formatLargeNumber(Number(value)), yLabel || 'Value']}
              contentStyle={{ 
                backgroundColor: 'rgba(255, 255, 255, 0.95)', 
                border: '1px solid #e5e7eb',
                borderRadius: '8px'
              }}
            />
            <Line 
              type="monotone" 
              dataKey={yDataKey} 
              stroke={CHART_COLORS[0]} 
              strokeWidth={3} 
              dot={{ r: 5, fill: CHART_COLORS[0] }}
              activeDot={{ r: 7 }}
            />
          </LineChart>
        );
      
      case 'pie':
        return (
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              outerRadius={100}
              dataKey={yDataKey}
              nameKey={xDataKey}
              label={({name, value, percent}) => `${name}: ${(percent * 100).toFixed(1)}%`}
              labelLine={false}
            >
              {data.map((_, index) => (
                <Cell key={index} fill={CHART_COLORS[index % CHART_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip 
              formatter={(value) => [formatLargeNumber(Number(value)), yLabel || 'Value']}
              contentStyle={{ 
                backgroundColor: 'rgba(255, 255, 255, 0.95)', 
                border: '1px solid #e5e7eb',
                borderRadius: '8px'
              }}
            />
            <Legend />
          </PieChart>
        );
      
      case 'area':
        if (isMultiSeries && seriesKeys) {
          return (
            <AreaChart {...commonProps}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey={xDataKey} fontSize={12} />
              <YAxis tickFormatter={formatLargeNumber} fontSize={12} />
              <Tooltip 
                formatter={(value, name) => [formatLargeNumber(Number(value)), name]}
                contentStyle={{ 
                  backgroundColor: 'rgba(255, 255, 255, 0.95)', 
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px'
                }}
              />
              <Legend />
              {seriesKeys.map((key, index) => (
                <Area 
                  key={key}
                  type="monotone" 
                  dataKey={key} 
                  stroke={CHART_COLORS[index % CHART_COLORS.length]} 
                  fill={CHART_COLORS[index % CHART_COLORS.length]} 
                  fillOpacity={0.4} 
                  strokeWidth={2}
                />
              ))}
            </AreaChart>
          );
        }
        return (
          <AreaChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey={xDataKey} fontSize={12} />
            <YAxis tickFormatter={formatLargeNumber} fontSize={12} />
            <Tooltip 
              formatter={(value) => [formatLargeNumber(Number(value)), yLabel || 'Value']}
              contentStyle={{ 
                backgroundColor: 'rgba(255, 255, 255, 0.95)', 
                border: '1px solid #e5e7eb',
                borderRadius: '8px'
              }}
            />
            <Area 
              type="monotone" 
              dataKey={yDataKey} 
              stroke={CHART_COLORS[0]} 
              fill={CHART_COLORS[0]} 
              fillOpacity={0.4} 
              strokeWidth={2}
            />
          </AreaChart>
        );
      
      default:
        return (
          <BarChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={xDataKey} />
            <YAxis tickFormatter={formatLargeNumber} />
            <Tooltip formatter={(value) => formatLargeNumber(Number(value))} />
            <Bar dataKey={yDataKey} fill={CHART_COLORS[0]} />
          </BarChart>
        );
    }
  };

  return (
    <div className="my-6">
      <div className="flex items-center gap-2 mb-4 text-gray-700">
        <TrendingUp className="w-5 h-5 text-blue-600" />
        <h3 className="font-semibold text-lg">{title}</h3>
      </div>
      <div className="h-80 bg-white rounded-lg border border-gray-200 p-4">
        <ResponsiveContainer width="100%" height="100%">
          {renderChart()}
        </ResponsiveContainer>
      </div>
    </div>
  );
};

// Enhanced Markdown Parser with better list handling
const parseMarkdown = (text: string, tables: TableData[], graphs: GraphData[]): JSX.Element => {
  const elements: JSX.Element[] = [];
  const lines = text.split('\n');
  
  const currentElement: JSX.Element | null = null;
  let listItems: string[] = [];
  let orderedListItems: string[] = [];
  let inCodeBlock = false;
  let codeLines: string[] = [];
  let codeLanguage = '';
  
  const flushUnorderedList = () => {
    if (listItems.length > 0) {
      elements.push(
        <ul key={`list-${elements.length}`} className="list-disc list-inside mb-4 space-y-2 text-gray-700">
          {listItems.map((item, i) => (
            <li key={i} className="leading-relaxed" dangerouslySetInnerHTML={{ __html: formatInlineText(item) }} />
          ))}
        </ul>
      );
      listItems = [];
    }
  };

  const flushOrderedList = () => {
    if (orderedListItems.length > 0) {
      elements.push(
        <ol key={`olist-${elements.length}`} className="list-decimal list-inside mb-4 space-y-2 text-gray-700">
          {orderedListItems.map((item, i) => (
            <li key={i} className="leading-relaxed" dangerouslySetInnerHTML={{ __html: formatInlineText(item) }} />
          ))}
        </ol>
      );
      orderedListItems = [];
    }
  };

  const formatInlineText = (text: string): string => {
    return text
      // Bold text
      .replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold">$1</strong>')
      // Italic text
      .replace(/\*(.*?)\*/g, '<em class="italic">$1</em>')
      // Citations
      .replace(/\[\^(\d+)\]/g, '<sup class="text-xs text-blue-600">[$1]</sup>')
      // Code spans
      .replace(/`([^`]+)`/g, '<code class="bg-gray-100 px-1 py-0.5 rounded text-sm font-mono">$1</code>');
  };
  
  const flushCodeBlock = () => {
    if (codeLines.length > 0) {
      elements.push(
        <pre key={`code-${elements.length}`} className="bg-gray-100 rounded-lg p-4 mb-4 overflow-x-auto">
          <code className={`text-sm ${codeLanguage ? `language-${codeLanguage}` : ''}`}>
            {codeLines.join('\n')}
          </code>
        </pre>
      );
      codeLines = [];
      codeLanguage = '';
    }
  };
  
  lines.forEach((line, i) => {
    // Handle code blocks
    if (line.startsWith('```')) {
      if (inCodeBlock) {
        flushCodeBlock();
        inCodeBlock = false;
      } else {
        flushUnorderedList();
        flushOrderedList();
        inCodeBlock = true;
        codeLanguage = line.slice(3).trim();
      }
      return;
    }
    
    if (inCodeBlock) {
      codeLines.push(line);
      return;
    }
    
    // Handle component placeholders
    if (line.includes('<!-- TABLE_')) {
      flushUnorderedList();
      flushOrderedList();
      const tableIndex = parseInt(line.match(/<!-- TABLE_(\d+) -->/)?.[1] || '0');
      if (tables[tableIndex]) {
        elements.push(<Table key={`table-${tableIndex}`} {...tables[tableIndex]} />);
      }
      return;
    }
    
    if (line.includes('<!-- GRAPH_')) {
      flushUnorderedList();
      flushOrderedList();
      const graphIndex = parseInt(line.match(/<!-- GRAPH_(\d+) -->/)?.[1] || '0');
      if (graphs[graphIndex]) {
        elements.push(<Chart key={`graph-${graphIndex}`} graph={graphs[graphIndex]} />);
      }
      return;
    }
    
    // Handle headings
    if (line.startsWith('# ')) {
      flushUnorderedList();
      flushOrderedList();
      elements.push(
        <h1 key={i} className="text-3xl font-bold text-gray-900 mb-6 mt-8 first:mt-0">
          {line.slice(2)}
        </h1>
      );
    } else if (line.startsWith('## ')) {
      flushUnorderedList();
      flushOrderedList();
      elements.push(
        <h2 key={i} className="text-2xl font-semibold text-gray-800 mb-4 mt-6">
          {line.slice(3)}
        </h2>
      );
    } else if (line.startsWith('### ')) {
      flushUnorderedList();
      flushOrderedList();
      elements.push(
        <h3 key={i} className="text-xl font-medium text-gray-800 mb-3 mt-5">
          {line.slice(4)}
        </h3>
      );
    } else if (line.startsWith('#### ')) {
      flushUnorderedList();
      flushOrderedList();
      elements.push(
        <h4 key={i} className="text-lg font-medium text-gray-700 mb-2 mt-4">
          {line.slice(5)}
        </h4>
      );
    } 
    // Handle unordered lists
    else if (line.match(/^\s*[-*+]\s+/)) {
      flushOrderedList();
      const item = line.replace(/^\s*[-*+]\s+/, '');
      listItems.push(item);
    } 
    // Handle ordered lists - improved regex to handle complex content
    else if (line.match(/^\s*\d+\.\s+/)) {
      flushUnorderedList();
      const item = line.replace(/^\s*\d+\.\s+/, '');
      orderedListItems.push(item);
    }
    // Handle empty lines
    else if (line.trim() === '') {
      flushUnorderedList();
      flushOrderedList();
      if (elements.length > 0 && !elements[elements.length - 1]?.key?.toString().includes('spacer')) {
        elements.push(<div key={`spacer-${i}`} className="mb-4" />);
      }
    }
    // Handle regular paragraphs
    else {
      flushUnorderedList();
      flushOrderedList();
      elements.push(
        <p key={i} className="mb-4 text-gray-700 leading-relaxed" dangerouslySetInnerHTML={{ __html: formatInlineText(line) }} />
      );
    }
  });
  
  flushUnorderedList();
  flushOrderedList();
  flushCodeBlock();
  
  return <div className="prose prose-lg max-w-none">{elements}</div>;
};

// Action Buttons Component
const ActionButtons = ({ content, onRegenerate }) => {
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
    <div className="flex justify-center gap-3 mt-8 pt-4 border-t border-gray-100">
      <button
        onClick={handleCopy}
        className="flex items-center justify-center p-2 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors"
        title={copied ? "Copied!" : "Copy response"}
      >
        <Copy className="w-4 h-4" />
      </button>
      
      {onRegenerate && (
        <button
          onClick={onRegenerate}
          className="flex items-center justify-center p-2 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors"
          title="Regenerate response"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
      )}
    </div>
  );
};

// Test component to demonstrate the new format
const TestNewFormat = () => {
  const testContent = `
**EXECUTIVE SUMMARY**
The employment rates in the United States and the European Union have shown notable differences from 2000 to 2024.

<GRAPH_DATA>
{
  "type": "line",
  "title": "Employment Rate Comparison: US vs EU (2000-2024)",
  "series": [
    {
      "name": "United States",
      "data": [
        { "x": "2000", "y": 64.5 },
        { "x": "2005", "y": 66.0 },
        { "x": "2010", "y": 58.5 },
        { "x": "2015", "y": 59.5 },
        { "x": "2020", "y": 56.0 },
        { "x": "2024", "y": 60.5 }
      ]
    },
    {
      "name": "European Union",
      "data": [
        { "x": "2000", "y": 61.0 },
        { "x": "2005", "y": 63.5 },
        { "x": "2010", "y": 64.0 },
        { "x": "2015", "y": 66.0 },
        { "x": "2020", "y": 65.0 },
        { "x": "2024", "y": 67.5 }
      ]
    }
  ],
  "xLabel": "Year",
  "yLabel": "Employment Rate (%)"
}
</GRAPH_DATA>

This shows the corrected multi-series format working properly.
`;

  return <ContentRenderer content={testContent} userQuery="Test new format" />;
};

// Main Component
export default function ContentRenderer({ content, userQuery, onRegenerate }) {
  const [isStreaming, setIsStreaming] = useState(false);
  
  // Detect if content is likely still streaming
  const detectStreaming = useMemo(() => {
    if (!content) return false;
    
    // Check for incomplete data blocks
    const hasIncompleteTable = content.includes('<TABLE_DATA>') && !content.includes('</TABLE_DATA>');
    const hasIncompleteGraph = content.includes('<GRAPH_DATA>') && !content.includes('</GRAPH_DATA>');
    
    return hasIncompleteTable || hasIncompleteGraph;
  }, [content]);
  
  // Update streaming state
  useEffect(() => {
    setIsStreaming(detectStreaming);
  }, [detectStreaming]);
  
  // Only parse when not streaming or when we have complete blocks
  const { graphs, tables, textContent } = useMemo(() => {
    console.log('ContentRenderer parsing - Streaming detected:', detectStreaming);
    
    if (detectStreaming) {
      console.log('Skipping parse due to incomplete streaming data');
      // Return content as-is while streaming
      return { graphs: [], tables: [], textContent: content || '' };
    }
    
    return parseContent(content);
  }, [content, detectStreaming]);
  
  // Show a streaming indicator if we detect incomplete blocks
  if (isStreaming) {
    return (
      <div className="w-full">
        <div className="text-gray-800">
          {/* Show partial content while streaming */}
          <div className="prose prose-lg max-w-none">
            {textContent.split('\n').map((line, index) => {
              // Skip lines that contain incomplete data blocks
              if (line.includes('<TABLE_DATA>') || line.includes('<GRAPH_DATA>')) {
                return null;
              }
              return line.trim() ? (
                <p key={index} className="mb-4 text-gray-700 leading-relaxed">
                  {line}
                </p>
              ) : null;
            })}
          </div>
          
          {/* Streaming indicator */}
          <div className="flex items-center gap-2 text-blue-600 mt-4">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
            <span className="text-sm">Processing data visualizations...</span>
          </div>
        </div>
      </div>
    );
  }
  
  return (
    <div className="w-full">
      <div className="text-gray-800">
        {/* Render markdown with embedded tables and graphs */}
        {textContent && parseMarkdown(textContent, tables, graphs)}
        
        {/* Fallback: render orphaned tables and graphs */}
        {tables.map((table, index) => {
          if (!textContent.includes(`<!-- TABLE_${index} -->`)) {
            return <Table key={`orphan-table-${index}`} {...table} />;
          }
          return null;
        })}
        
        {graphs.map((graph, index) => {
          if (!textContent.includes(`<!-- GRAPH_${index} -->`)) {
            return <Chart key={`orphan-graph-${index}`} graph={graph} />;
          }
          return null;
        })}
        
        {/* Action buttons */}
        <ActionButtons content={content} onRegenerate={onRegenerate} />
      </div>
    </div>
  );
}

// Alternative: Debounced approach
export function ContentRendererDebounced({ content, userQuery, onRegenerate }) {
  const [debouncedContent, setDebouncedContent] = useState(content);
  
  // Debounce content updates to wait for streaming to complete
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedContent(content);
    }, 500); // Wait 500ms for streaming to complete
    
    return () => clearTimeout(timer);
  }, [content]);
  
  const { graphs, tables, textContent } = useMemo(() => {
    return parseContent(debouncedContent);
  }, [debouncedContent]);
  
  return (
    <div className="w-full">
      <div className="text-gray-800">
        {textContent && parseMarkdown(textContent, tables, graphs)}
        <ActionButtons content={content} onRegenerate={onRegenerate} />
      </div>
    </div>
  );
}
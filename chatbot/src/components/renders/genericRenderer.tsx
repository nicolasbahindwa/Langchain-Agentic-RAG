import React, { useState, useMemo } from 'react';
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
import { Info, BarChart3, Grid3x3, Image, AlertCircle, TrendingUp } from 'lucide-react';

// Types
interface GraphData {
  type: 'bar' | 'line' | 'pie' | 'area' | 'scatter' | 'composed' | 'radar';
  title: string;
  data: Array<{ [key: string]: any }>;
  xLabel?: string;
  yLabel?: string;
  xDataKey?: string;
  yDataKey?: string;
}

interface TableData {
  headers: string[];
  rows: string[][];
  title?: string;
}

interface DualDisplayData {
  table: TableData;
  graph: GraphData;
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

// Parser Functions
const parseContent = (content: string) => {
  const graphs: GraphData[] = [];
  const tables: TableData[] = [];
  const dualDisplayData: DualDisplayData[] = [];
  
  // Parse table data
  const tableMatches = [...content.matchAll(/<TABLE_DATA>\s*(\{.*?\})\s*<\/TABLE_DATA>/gs)];
  tableMatches.forEach(match => {
    try {
      const jsonData = JSON.parse(match[1].trim());
      if (jsonData.columns && jsonData.rows) {
        const tableData: TableData = {
          headers: jsonData.columns,
          rows: jsonData.rows
        };
        tables.push(tableData);
      }
    } catch (e) {
      console.error('Error parsing table data:', e);
    }
  });

  // Parse graph data
  const graphMatches = [...content.matchAll(/<GRAPH_DATA>\s*(\{.*?\})\s*<\/GRAPH_DATA>/gs)];
  graphMatches.forEach(match => {
    try {
      const jsonData = JSON.parse(match[1].trim());
      if (jsonData.type && jsonData.title && jsonData.data) {
        const graphData: GraphData = {
          type: jsonData.type,
          title: jsonData.title,
          data: jsonData.data,
          xLabel: jsonData.xLabel,
          yLabel: jsonData.yLabel,
          xDataKey: jsonData.xDataKey || 'x',
          yDataKey: jsonData.yDataKey || 'y'
        };
        graphs.push(graphData);
      }
    } catch (e) {
      console.error('Error parsing graph data:', e);
    }
  });
  
  // Clean text content
  const textContent = content
    .replace(/<TABLE_DATA>.*?<\/TABLE_DATA>/gs, '')
    .replace(/<GRAPH_DATA>.*?<\/GRAPH_DATA>/gs, '')
    .trim();
  
  return { graphs, tables, textContent, dualDisplayData };
};

// Components
const Table = ({ headers, rows, className = '' }) => (
  <div className={`w-full ${className}`}>
    <div className="overflow-x-auto rounded-lg border border-gray-300 shadow-sm">
      <table className="min-w-full divide-y divide-gray-200 bg-white">
        <thead className="bg-gradient-to-r from-gray-50 to-gray-100">
          <tr>
            {headers.map((header, i) => (
              <th 
                key={i} 
                className="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider border-r border-gray-200 last:border-r-0"
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
                  className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 border-r border-gray-200 last:border-r-0"
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

const ChartContainer = ({ children, title }) => (
  <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
    <div className="flex items-center gap-2 p-4 border-b border-gray-100 text-blue-600">
      <TrendingUp className="w-5 h-5" />
      <h3 className="font-semibold text-lg">{title}</h3>
    </div>
    <div className="p-4">
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          {children}
        </ResponsiveContainer>
      </div>
    </div>
  </div>
);

const renderChart = (graph: GraphData) => {
  const { type, data, xLabel, yLabel, xDataKey, yDataKey } = graph;
  const commonProps = { 
    data, 
    margin: { top: 20, right: 30, left: 20, bottom: 20 } 
  };

  switch (type) {
    case 'bar':
      return (
        <BarChart {...commonProps}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={xDataKey} label={xLabel} angle={-45} textAnchor="end" height={60} />
          <YAxis label={yLabel} tickFormatter={formatLargeNumber} />
          <Tooltip formatter={(value) => formatLargeNumber(Number(value))} />
          <Legend />
          <Bar dataKey={yDataKey} fill={CHART_COLORS[0]} />
        </BarChart>
      );
    
    case 'line':
      return (
        <LineChart {...commonProps}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={xDataKey} label={xLabel} angle={-45} textAnchor="end" height={60} />
          <YAxis label={yLabel} tickFormatter={formatLargeNumber} />
          <Tooltip formatter={(value) => formatLargeNumber(Number(value))} />
          <Legend />
          <Line type="monotone" dataKey={yDataKey} stroke={CHART_COLORS[0]} strokeWidth={2} dot={{ r: 4 }} />
        </LineChart>
      );
    
    case 'pie':
      return (
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            outerRadius={80}
            dataKey={yDataKey}
            nameKey={xDataKey}
            label={({name, value}) => `${name}: ${formatLargeNumber(value)}`}
          >
            {data.map((_, index) => (
              <Cell key={index} fill={CHART_COLORS[index % CHART_COLORS.length]} />
            ))}
          </Pie>
          <Tooltip formatter={(value) => formatLargeNumber(Number(value))} />
          <Legend />
        </PieChart>
      );
    
    case 'area':
      return (
        <AreaChart {...commonProps}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={xDataKey} label={xLabel} angle={-45} textAnchor="end" height={60} />
          <YAxis label={yLabel} tickFormatter={formatLargeNumber} />
          <Tooltip formatter={(value) => formatLargeNumber(Number(value))} />
          <Legend />
          <Area type="monotone" dataKey={yDataKey} stroke={CHART_COLORS[0]} fill={CHART_COLORS[0]} fillOpacity={0.3} />
        </AreaChart>
      );
    
    case 'scatter':
      return (
        <ScatterChart {...commonProps}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={xDataKey} label={xLabel} />
          <YAxis dataKey={yDataKey} label={yLabel} tickFormatter={formatLargeNumber} />
          <Tooltip formatter={(value) => formatLargeNumber(Number(value))} />
          <Legend />
          <Scatter dataKey={yDataKey} fill={CHART_COLORS[0]} />
        </ScatterChart>
      );
    
    case 'composed':
      return (
        <ComposedChart {...commonProps}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={xDataKey} label={xLabel} angle={-45} textAnchor="end" height={60} />
          <YAxis label={yLabel} tickFormatter={formatLargeNumber} />
          <Tooltip formatter={(value) => formatLargeNumber(Number(value))} />
          <Legend />
          <Bar dataKey={yDataKey} fill={CHART_COLORS[0]} />
          <Line type="monotone" dataKey={yDataKey} stroke={CHART_COLORS[1]} strokeWidth={2} />
        </ComposedChart>
      );
    
    case 'radar':
      return (
        <RadarChart data={data} outerRadius="80%">
          <PolarGrid />
          <PolarAngleAxis dataKey={xDataKey} />
          <PolarRadiusAxis angle={30} domain={[0, 'dataMax']} />
          <Radar name={yDataKey} dataKey={yDataKey} stroke={CHART_COLORS[0]} fill={CHART_COLORS[0]} fillOpacity={0.6} />
          <Legend />
          <Tooltip formatter={(value) => formatLargeNumber(Number(value))} />
        </RadarChart>
      );
    
    default:
      return null;
  }
};

const Alert = ({ children, variant = 'info' }) => {
  const styles = {
    info: 'bg-blue-50 border-blue-200 text-blue-800',
    warning: 'bg-yellow-50 border-yellow-200 text-yellow-800'
  };
  
  return (
    <div className={`flex items-start gap-3 p-4 rounded-lg border ${styles[variant]}`}>
      <Info className="w-5 h-5 mt-0.5 flex-shrink-0" />
      <div className="text-sm">{children}</div>
    </div>
  );
};

// Markdown Parser
const parseMarkdown = (text: string): JSX.Element => {
  const elements: JSX.Element[] = [];
  const lines = text.split('\n');
  
  lines.forEach((line, i) => {
    if (line.startsWith('# ')) {
      elements.push(<h1 key={i} className="text-3xl font-bold text-gray-900 mb-4">{line.slice(2)}</h1>);
    } else if (line.startsWith('## ')) {
      elements.push(<h2 key={i} className="text-2xl font-semibold text-gray-800 mb-3">{line.slice(3)}</h2>);
    } else if (line.startsWith('### ')) {
      elements.push(<h3 key={i} className="text-xl font-medium text-gray-800 mb-3">{line.slice(4)}</h3>);
    } else if (line.trim() === '') {
      elements.push(<div key={i} className="mb-4" />);
    } else {
      elements.push(<p key={i} className="mb-4 text-gray-700 leading-relaxed">{line}</p>);
    }
  });
  
  return <div className="prose prose-lg max-w-none">{elements}</div>;
};

// Main Component
export default function ContentRenderer({ content }) {
  const { graphs, tables, textContent } = useMemo(() => parseContent(content), [content]);
  
  return (
    <div className="max-w-6xl mx-auto p-6 space-y-8 bg-gray-50 min-h-screen">
      {/* Markdown Content */}
      {textContent && (
        <div className="bg-white rounded-lg p-6 shadow-sm">
          {parseMarkdown(textContent)}
        </div>
      )}

      {/* Tables */}
      {tables.map((table, index) => (
        <div key={`table-${index}`} className="space-y-4">
          <div className="flex items-center gap-2 text-green-600">
            <Grid3x3 className="w-5 h-5" />
            <h3 className="font-semibold text-lg">Data Table {index + 1}</h3>
          </div>
          <div className="bg-white rounded-lg p-6 shadow-sm">
            <Table headers={table.headers} rows={table.rows} />
          </div>
        </div>
      ))}

      {/* Graphs */}
      {graphs.map((graph, index) => (
        <ChartContainer key={`graph-${index}`} title={graph.title}>
          {renderChart(graph)}
        </ChartContainer>
      ))}

      {/* No content message */}
      {graphs.length === 0 && tables.length === 0 && !textContent && (
        <Alert variant="info">
          No structured content detected. The renderer supports markdown text, tables, and graphs.
        </Alert>
      )}
    </div>
  );
}
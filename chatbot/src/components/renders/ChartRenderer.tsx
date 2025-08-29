import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, BarChart, Bar, PieChart, Pie, Cell, ScatterChart, Scatter, AreaChart, Area, ResponsiveContainer } from 'recharts';

const COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#06B6D4', '#F97316', '#84CC16'];

interface GraphData {
  type: string;
  title: string;
  data: any[];
  xKey?: string;
  yKey?: string;
  description?: string;
}

interface ParsedContent {
  type: 'text' | 'table' | 'graph' | 'mixed';
  content: any;
}

// Enhanced parser that handles various formats from LLM responses
export const parseGraphData = (content: string): GraphData | null => {
  try {
    const lines = content.split('\n').map(line => line.trim()).filter(line => line);
    let title = '';
    let type = 'bar';
    let description = '';
    let xData: string[] = [];
    let yData: number[] = [];

    for (const line of lines) {
      // Parse GRAPH line for type and title
      if (line.startsWith('GRAPH:')) {
        const graphInfo = line.replace('GRAPH:', '').trim();
        
        // Extract chart type
        if (graphInfo.toLowerCase().includes('bar')) type = 'bar';
        else if (graphInfo.toLowerCase().includes('line')) type = 'line';
        else if (graphInfo.toLowerCase().includes('pie')) type = 'pie';
        else if (graphInfo.toLowerCase().includes('scatter')) type = 'scatter';
        else if (graphInfo.toLowerCase().includes('area')) type = 'area';
        
        // Extract title - everything after "showing"
        const showingIndex = graphInfo.toLowerCase().indexOf('showing');
        if (showingIndex !== -1) {
          title = graphInfo.substring(showingIndex + 7).trim();
        } else {
          title = graphInfo.replace(/^(bar|line|pie|scatter|area)\s*(chart|graph)?\s*/i, '').trim();
        }
      }
      
      // Parse DATA line with flexible format support
      else if (line.startsWith('DATA:')) {
        const dataStr = line.replace('DATA:', '').trim();
        
        // Format 1: "x=[...], y=[...]"
        const xMatch = dataStr.match(/x\s*=\s*\[(.*?)\]/);
        const yMatch = dataStr.match(/y\s*=\s*\[(.*?)\]/);
        
        if (xMatch && yMatch) {
          xData = parseArrayString(xMatch[1]);
          yData = parseNumericArrayString(yMatch[1]);
        }
        
        // Format 2: "- x = [...] - y = [...]" 
        else {
          const parts = dataStr.split(' - ');
          for (const part of parts) {
            if (part.includes('x =')) {
              const xPart = extractArrayContent(part);
              if (xPart) xData = parseArrayString(xPart);
            }
            if (part.includes('y =')) {
              const yPart = extractArrayContent(part);
              if (yPart) yData = parseNumericArrayString(yPart);
            }
          }
        }
      }
      
      // Capture description lines (non-directive lines)
      else if (!line.startsWith('GRAPH:') && !line.startsWith('DATA:') && line.length > 10) {
        if (description) description += ' ';
        description += line;
      }
    }

    // Create chart data if we have both x and y data
    if (xData.length > 0 && yData.length > 0) {
      const data = xData.map((name, index) => ({
        name,
        value: yData[index] || 0,
        x: name,
        y: yData[index] || 0
      }));

      return {
        type: type.toLowerCase(),
        title: title || 'Data Visualization',
        data,
        xKey: 'name',
        yKey: 'value',
        description: description || undefined
      };
    }

    return null;
  } catch (error) {
    console.error('Error parsing graph data:', error);
    return null;
  }
};

// Helper functions
const extractArrayContent = (str: string): string | null => {
  const match = str.match(/\[(.*?)\]/);
  return match ? match[1] : null;
};

const parseArrayString = (arrayStr: string): string[] => {
  return arrayStr
    .split(',')
    .map(item => item.trim().replace(/['"]/g, ''))
    .filter(item => item);
};

const parseNumericArrayString = (arrayStr: string): number[] => {
  return arrayStr
    .split(',')
    .map(item => {
      const cleaned = item.trim().replace(/['"]/g, '');
      // Extract numeric value from strings like "26.9 trillion", "$1.2B", "15.3%"
      const numberMatch = cleaned.match(/[\d.,]+/);
      if (numberMatch) {
        let value = parseFloat(numberMatch[0].replace(/,/g, ''));
        
        // Handle unit conversions
        const lowerItem = cleaned.toLowerCase();
        if (lowerItem.includes('trillion')) value *= 1000;
        else if (lowerItem.includes('billion') || lowerItem.includes('b')) value *= 1;
        else if (lowerItem.includes('million') || lowerItem.includes('m')) value /= 1000;
        
        return value;
      }
      return 0;
    })
    .filter(item => !isNaN(item));
};

// Main content parser function
export const parseContent = (content: string, userQuery: string = ''): ParsedContent => {
  const normalizedContent = content.trim();
  
  // Check if user explicitly requested a chart/graph
  const userRequestsChart = userQuery.toLowerCase().match(
    /\b(chart|graph|plot|visualize|display.*chart|show.*graph|bar chart|line chart|pie chart)\b/
  );
  
  // Check for graph content
  if (normalizedContent.includes('GRAPH:') && normalizedContent.includes('DATA:')) {
    const graphData = parseGraphData(normalizedContent);
    if (graphData && graphData.data.length > 0) {
      return { type: 'graph', content: graphData };
    }
  }
  
  return { type: 'text', content: normalizedContent };
};

// Main Chart Renderer Component - Ready for export and reuse
const ChartRenderer: React.FC<{ graphData: GraphData }> = ({ graphData }) => {
  const { type, title, data, description } = graphData;

  if (!data || data.length === 0) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 my-4">
        <p className="text-red-700 text-center">No data available for visualization</p>
      </div>
    );
  }

  const getYAxisLabel = (data: any[]): string => {
    if (data.length === 0) return '';
    
    const firstValue = data[0].value;
    if (typeof firstValue === 'number') {
      if (firstValue >= 1000) return 'Trillions USD';
      if (firstValue >= 1) return 'Billions USD';
      if (firstValue < 1) return 'Value';
    }
    return 'Value';
  };

  const formatTooltipValue = (value: any): string => {
    if (typeof value === 'number') {
      if (value >= 1000) return `${value.toLocaleString()} trillion USD`;
      if (value >= 1) return `${value.toLocaleString()} billion USD`;
      return value.toLocaleString();
    }
    return String(value);
  };

  const renderChart = () => {
    const commonMargin = { top: 20, right: 30, left: 40, bottom: 80 };
    
    switch (type) {
      case 'bar':
        return (
          <ResponsiveContainer width="100%" height={450}>
            <BarChart data={data} margin={commonMargin}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis 
                dataKey="name" 
                angle={-45}
                textAnchor="end"
                height={100}
                interval={0}
                tick={{ fontSize: 12 }}
              />
              <YAxis 
                tick={{ fontSize: 12 }}
                label={{ value: getYAxisLabel(data), angle: -90, position: 'insideLeft' }}
              />
              <Tooltip 
                formatter={(value) => [formatTooltipValue(value), 'Value']}
                labelStyle={{ color: '#374151' }}
                contentStyle={{ backgroundColor: '#f9fafb', border: '1px solid #d1d5db' }}
              />
              <Bar dataKey="value" fill={COLORS[0]} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        );
      
      case 'pie':
        return (
          <ResponsiveContainer width="100%" height={450}>
            <PieChart>
              <Pie 
                data={data} 
                cx="50%" 
                cy="50%" 
                outerRadius={120} 
                label={({ name, value, percent }) => 
                  `${name}: ${(percent! * 100).toFixed(1)}%`
                }
                dataKey="value"
                labelLine={false}
              >
                {data.map((_, i) => (
                  <Cell key={`cell-${i}`} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(value) => [formatTooltipValue(value), 'Value']} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        );

      case 'scatter':
        return (
          <ResponsiveContainer width="100%" height={450}>
            <ScatterChart data={data} margin={commonMargin}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="x" 
                tick={{ fontSize: 12 }}
                angle={-45}
                textAnchor="end"
                height={100}
              />
              <YAxis 
                dataKey="y" 
                tick={{ fontSize: 12 }}
                label={{ value: getYAxisLabel(data), angle: -90, position: 'insideLeft' }}
              />
              <Tooltip formatter={(value) => [formatTooltipValue(value), 'Value']} />
              <Scatter name="Data Points" dataKey="y" fill={COLORS[0]} />
            </ScatterChart>
          </ResponsiveContainer>
        );

      case 'area':
        return (
          <ResponsiveContainer width="100%" height={450}>
            <AreaChart data={data} margin={commonMargin}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="name" 
                angle={-45}
                textAnchor="end"
                height={100}
                tick={{ fontSize: 12 }}
              />
              <YAxis 
                tick={{ fontSize: 12 }}
                label={{ value: getYAxisLabel(data), angle: -90, position: 'insideLeft' }}
              />
              <Tooltip formatter={(value) => [formatTooltipValue(value), 'Value']} />
              <Area 
                type="monotone" 
                dataKey="value" 
                stroke={COLORS[0]} 
                fill={COLORS[0]} 
                fillOpacity={0.3} 
                strokeWidth={3}
              />
            </AreaChart>
          </ResponsiveContainer>
        );
      
      case 'line':
      default:
        return (
          <ResponsiveContainer width="100%" height={450}>
            <LineChart data={data} margin={commonMargin}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="name" 
                angle={-45}
                textAnchor="end"
                height={100}
                interval={0}
                tick={{ fontSize: 12 }}
              />
              <YAxis 
                tick={{ fontSize: 12 }}
                label={{ value: getYAxisLabel(data), angle: -90, position: 'insideLeft' }}
              />
              <Tooltip formatter={(value) => [formatTooltipValue(value), 'Value']} />
              <Line 
                type="monotone" 
                dataKey="value" 
                stroke={COLORS[0]} 
                strokeWidth={3}
                dot={{ fill: COLORS[0], strokeWidth: 2, r: 4 }}
                activeDot={{ r: 6, stroke: COLORS[0], strokeWidth: 2 }}
              />
            </LineChart>
          </ResponsiveContainer>
        );
    }
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 my-4 shadow-sm">
      {title && (
        <h4 className="text-xl font-semibold text-gray-800 mb-6 text-center">
          {title}
        </h4>
      )}
      <div className="w-full">
        {renderChart()}
      </div>
      {description && (
        <p className="text-sm text-gray-600 mt-4 text-center italic leading-relaxed px-4">
          {description}
        </p>
      )}
    </div>
  );
};

export default ChartRenderer;
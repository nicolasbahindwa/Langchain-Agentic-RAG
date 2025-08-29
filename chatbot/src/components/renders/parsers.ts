export interface ParsedContent {
  type: 'text' | 'table' | 'graph' | 'mixed';
  content: any;
}

export interface GraphData {
  type: string;
  title: string;
  data: any[];
  xKey?: string;
  yKey?: string;
  description?: string;
}

export interface TableData {
  headers: string[];
  rows: string[][];
  title?: string;
}

// Helper function to convert table data to chart data if user requested a chart
const convertTableToChart = (tableData: TableData, userQuery: string): GraphData | null => {
  try {
    const { headers, rows, title } = tableData;
    
    if (rows.length === 0 || headers.length < 2) return null;
    
    // Determine chart type based on user query
    const query = userQuery.toLowerCase();
    let chartType = 'bar'; // default
    
    if (query.includes('line chart') || query.includes('trend')) {
      chartType = 'line';
    } else if (query.includes('pie chart') || query.includes('proportion')) {
      chartType = 'pie';
    } else if (query.includes('bar chart') || query.includes('comparison') || query.includes('top ')) {
      chartType = 'bar';
    }
    
    // Convert table data to chart data
    // Assume first column is labels, second column is values
    const data = rows.map(row => {
      const name = String(row[0] || '');
      const valueStr = String(row[1] || '0');
      // Extract numbers from strings like "$1.2B", "15.3%", etc.
      const valueMatch = valueStr.match(/[\d,.]+/);
      const value = valueMatch ? parseFloat(valueMatch[0].replace(/,/g, '')) : 0;
      
      return {
        name,
        value,
        x: name,
        y: value
      };
    }).filter(item => item.value > 0); // Filter out zero values
    
    return {
      type: chartType,
      title: title || 'Data Visualization',
      data,
      xKey: 'name',
      yKey: 'value',
      description: `Converted from table data based on user request for ${chartType} chart`
    };
  } catch (error) {
    console.error('Error converting table to chart:', error);
    return null;
  }
};

export const parseGraphData = (graphText: string): GraphData | null => {
  try {
    const lines = graphText.split('\n');
    let title = '';
    let type = 'line';
    let data: any[] = [];
    let description = '';

    for (const line of lines) {
      if (line.startsWith('GRAPH:')) {
        const graphInfo = line.replace('GRAPH:', '').trim();
        const parts = graphInfo.split(' showing ');
        if (parts.length >= 2) {
          type = parts[0].toLowerCase();
          title = parts[1];
        } else {
          title = graphInfo;
        }
      } else if (line.startsWith('DATA:')) {
        const dataStr = line.replace('DATA:', '').trim();
        
        // Handle different data formats
        if (dataStr.includes('x=') && dataStr.includes('y=')) {
          // Format: x=[1,2,3], y=[10,20,30]
          const xMatch = dataStr.match(/x=\[(.*?)\]/);
          const yMatch = dataStr.match(/y=\[(.*?)\]/);
          
          if (xMatch && yMatch) {
            const xValues = xMatch[1].split(',').map(v => v.trim().replace(/['"]/g, ''));
            const yValues = yMatch[1].split(',').map(v => {
              const cleaned = v.trim().replace(/['"]/g, '');
              return parseFloat(cleaned) || cleaned;
            });
            
            data = xValues.map((x, i) => ({
              x: isNaN(parseFloat(x)) ? x : parseFloat(x),
              y: yValues[i] || 0,
              name: x,
              value: yValues[i] || 0
            }));
          }
        } else if (dataStr.includes('[') && dataStr.includes(']')) {
          // Handle JSON-like data
          try {
            const jsonStr = dataStr.replace(/(\w+)=/g, '"$1":').replace(/'/g, '"');
            data = JSON.parse(jsonStr);
          } catch (e) {
            // Fallback parsing
            console.warn('Could not parse graph data:', e);
          }
        }
      } else if (line.trim() && !line.startsWith('GRAPH:') && !line.startsWith('DATA:')) {
        description += line + ' ';
      }
    }

    return {
      type: type.toLowerCase(),
      title,
      data,
      xKey: 'x',
      yKey: 'y',
      description: description.trim()
    };
  } catch (error) {
    console.error('Error parsing graph data:', error);
    return null;
  }
};

export const parseTableData = (tableText: string): TableData | null => {
  try {
    const lines = tableText.split('\n').filter(line => line.trim());
    let title = '';
    let headers: string[] = [];
    let rows: string[][] = [];
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      
      if (line.startsWith('TABLE:') || line.startsWith('#')) {
        title = line.replace(/^(TABLE:|#+)\s*/, '');
      } else if (line.includes('|')) {
        const cells = line.split('|').map(cell => cell.trim()).filter(cell => cell);
        
        if (headers.length === 0 && cells.length > 0) {
          headers = cells;
        } else if (cells.length > 0 && !line.includes('---')) {
          rows.push(cells);
        }
      }
    }
    
    if (headers.length === 0 && rows.length > 0) {
      headers = rows[0];
      rows = rows.slice(1);
    }
    
    return { headers, rows, title };
  } catch (error) {
    console.error('Error parsing table data:', error);
    return null;
  }
};

// Enhanced parseContent with user query context
export const parseContent = (content: string, userQuery: string = ''): ParsedContent => {
  const normalizedContent = content.trim();
  
  // Check if user explicitly requested a chart/graph
  const userRequestsChart = userQuery.toLowerCase().match(
    /\b(chart|graph|plot|visualize|display.*chart|show.*graph|bar chart|line chart|pie chart)\b/
  );
  
  // Check for graph content first
  if (normalizedContent.includes('GRAPH:') || normalizedContent.match(/\b(bar|line|pie|scatter|area)\s+(chart|graph)/i)) {
    const graphData = parseGraphData(normalizedContent);
    if (graphData && graphData.data.length > 0) {
      return { type: 'graph', content: graphData };
    }
  }
  
  // Check for table content
  if (normalizedContent.includes('|') || normalizedContent.includes('TABLE:')) {
    const tableData = parseTableData(normalizedContent);
    if (tableData && tableData.headers.length > 0) {
      // If user requested a chart but got a table, try to convert
      if (userRequestsChart && tableData.rows.length > 0) {
        const chartData = convertTableToChart(tableData, userQuery);
        if (chartData) {
          console.log('Converted table to chart based on user request');
          return { type: 'graph', content: chartData };
        }
      }
      return { type: 'table', content: tableData };
    }
  }
  
  // Check for mixed content
  const hasGraph = normalizedContent.includes('GRAPH:') || normalizedContent.match(/\b(bar|line|pie|scatter|area)\s+(chart|graph)/i);
  const hasTable = normalizedContent.includes('|') && normalizedContent.split('\n').some(line => line.split('|').length > 2);
  
  if (hasGraph || hasTable) {
    return { type: 'mixed', content: normalizedContent };
  }
  
  return { type: 'text', content: normalizedContent };
};
import React from 'react';
import type { TableData } from './parsers';

const TableRenderer: React.FC<{ tableData: TableData }> = ({ tableData }) => {
  const { headers, rows, title } = tableData;

  if (!headers || headers.length === 0) {
    return <div className="bg-red-50 border border-red-200 rounded-lg p-4 my-4">Invalid table data</div>;
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 my-4 shadow-sm">
      {title && <h4 className="text-lg font-semibold text-gray-800 mb-3">{title}</h4>}
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse">
          <thead>
            <tr className="bg-gray-50">
              {headers.map((header, i) => (
                <th key={i} className="border border-gray-300 px-4 py-2 text-left text-sm font-semibold text-gray-700">{header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                {row.map((cell, j) => (
                  <td key={j} className="border border-gray-300 px-4 py-2 text-sm text-gray-600">{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default TableRenderer;

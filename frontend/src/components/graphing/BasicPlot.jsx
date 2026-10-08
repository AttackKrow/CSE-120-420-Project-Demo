import React, { useState, useEffect, useMemo } from 'react';
import Plot from 'react-plotly.js';

export default function LotHistorySankey() {
  const [searchLot, setSearchLot] = useState('');
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);

  // Fetch data from the Python backend
  useEffect(() => {
    if (!searchLot) return;
    
    const fetchHistory = async () => {
      setLoading(true);
      try {
        const response = await fetch(`http://127.0.0.1:8000/api/history/${searchLot}`);
        const data = await response.json();
        setEvents(data);
      } catch (error) {
        console.error("Failed to fetch lot history:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
  }, [searchLot]);

  const { nodes, links } = useMemo(() => {
    if (events.length === 0) return { nodes: [], links: [] };

    const nodeMap = new Map();
    const addNode = (uuid, name, seq, status) => {
      if (!uuid) return;
      if (!nodeMap.has(uuid)) {
        nodeMap.set(uuid, { label: `${name} (Seq ${seq}) [${status || 'ST_1'}]` });
      }
    };

    events.forEach(e => {
      if (e.in_lot_uuid) addNode(e.in_lot_uuid, e.in_lot_name, e.in_lot_sequence, e.in_lot_status);
      if (e.out_lot_uuid) addNode(e.out_lot_uuid, e.out_lot_name, e.out_lot_sequence, e.out_lot_status);
    });

    const nodeList = Array.from(nodeMap.keys());
    const nodeLabels = nodeList.map(uuid => nodeMap.get(uuid).label);
    const sankeyLinks = { source: [], target: [], value: [], label: [], color: [] }; // Added color array

    events.forEach(e => {
      let sourceIdx = nodeList.indexOf(e.in_lot_uuid);
      let targetIdx = nodeList.indexOf(e.out_lot_uuid);
      let linkValue = e.qty_in || 1;
      
      // Default link color (fallback)
      let linkColor = 'rgba(200, 200, 200, 0.4)'; 

      if (e.in_lot_uuid === null) {
        nodeList.push(`creation-${e.id}`);
        nodeLabels.push(`Creation (${e.segment_name})`);
        sourceIdx = nodeList.length - 1;
        linkValue = 5;
        linkColor = 'rgba(139, 92, 246, 0.5)'; // Purple for Creation
      } else if (e.out_lot_uuid === null) {
         nodeList.push(`disposal-${e.id}`);
         nodeLabels.push(`Disposal (${e.segment_name})`);
         targetIdx = nodeList.length - 1;
         linkColor = 'rgba(239, 68, 68, 0.5)'; // Red for Disposal
      } else {
         // Color logic based on lot names
         if (e.in_lot_name === e.out_lot_name) {
             // Process with same in and out names (Sequence Bump)
             linkColor = 'rgba(148, 163, 184, 0.4)'; // Gray
         } else if (e.in_lot_name !== searchLot && e.out_lot_name === searchLot) {
             // Input from a different lot merging into this lot
             linkColor = 'rgba(16, 185, 129, 0.5)'; // Green
         } else if (e.in_lot_name === searchLot && e.out_lot_name !== searchLot) {
             // Output splitting off to a different lot name
             linkColor = 'rgba(249, 115, 22, 0.5)'; // Orange
         }
      }

      if (sourceIdx !== -1 && targetIdx !== -1) {
        sankeyLinks.source.push(sourceIdx);
        sankeyLinks.target.push(targetIdx);
        sankeyLinks.value.push(linkValue);
        sankeyLinks.label.push(e.segment_name);
        sankeyLinks.color.push(linkColor); // Push the calculated color
      }
    });

    return { nodes: nodeLabels, links: sankeyLinks };
  }, [events]);

  return (
    <div className="flex flex-col w-full max-w-6xl mx-auto p-4 space-y-4">
      <div className="flex w-full space-x-4 mb-2">
        <input
          type="text"
          value={searchLot}
          onChange={(e) => {
            const sanitizedValue = e.target.value.replace(/[^a-zA-Z0-9_-]/g, '');
            setSearchLot(sanitizedValue);
          }
        }
          placeholder="Enter Lot Name..."
          className="border border-gray-300 p-2 rounded w-64 shadow-sm"
        />
      </div>

      <div className="bg-white border rounded shadow-sm p-4 w-full h-[600px]">
        {nodes.length > 0 ? (
          <Plot
            data={[
                {
                  type: 'sankey',
                  orientation: 'h',
                  node: {
                    pad: 15,
                    thickness: 30,
                    line: { color: 'black', width: 0.5 },
                    label: nodes,
                  },
                  link: {
                    source: links.source,
                    target: links.target,
                    value: links.value,
                    label: links.label,
                    color: links.color,
                  },
                },
              ]}
            layout={{ 
              title: `Genealogy Stream: ${searchLot}`, 
              font: { size: 11 },
              margin: { t: 40, l: 20, r: 20, b: 20 }
            }}
            config={{
              scrollZoom: true,
            }}
            useResizeHandler={true}
            style={{ width: '100%', height: '100%' }}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500">
            No history found for this lot.
          </div>
        )}
      </div>
    </div>
  );
}
import React, { useState, useEffect, useCallback } from 'react';
import ReactFlow, {
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';

const nodeWidth = 200;
const nodeHeight = 60;

// Dagre layout engine configuration
const getLayoutedElements = (nodes, edges, direction = 'LR') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({ rankdir: direction, ranksep: 350, nodesep: 100 });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      targetPosition: direction === 'LR' ? 'left' : 'top',
      sourcePosition: direction === 'LR' ? 'right' : 'bottom',
      position: {
        x: nodeWithPosition.x - nodeWidth / 2,
        y: nodeWithPosition.y - nodeHeight / 2,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
};

export default function LotHistoryDAG() {
  // Moved states inside the component
  const [searchLot, setSearchLot] = useState('CT000000');
  const [loading, setLoading] = useState(false);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [rfInstance, setRfInstance] = useState(null); 
  const [rawEvents, setRawEvents] = useState([]); 

  useEffect(() => {
    if (!searchLot) return;

    const fetchHistory = async () => {
      setLoading(true);
      try {
        const response = await fetch(`http://10.0.0.177:8000/api/history/${searchLot}`);
        const data = await response.json();
        setRawEvents(data);
        
        buildGraph(data);
      } catch (error) {
        console.error("Failed to fetch lot history:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
  }, [searchLot]);

  const buildGraph = useCallback((events) => {
    if (events.length === 0) {
      setNodes([]);
      setEdges([]);
      return;
    }

    const initialNodes = [];
    const initialEdges = [];
    const nodeSet = new Set();

    const addNode = (id, labelText, bgColor, textColor = 'black') => {
      if (!nodeSet.has(id)) {
        nodeSet.add(id);
        initialNodes.push({
          id,
          data: { label: labelText },
          style: {
            background: bgColor,
            color: textColor,
            border: '1px solid #222',
            borderRadius: '5px',
            fontSize: '12px',
            fontWeight: 'bold',
            width: nodeWidth,
          },
        });
      }
    };

    events.forEach((e) => {
      let sourceId = e.in_lot_uuid;
      let targetId = e.out_lot_uuid;

      // 1. Generate Nodes
      if (sourceId) {
        addNode(sourceId, `${e.in_lot_name} (Seq ${e.in_lot_sequence})`, '#f8fafc'); // Default white
      } else {
        sourceId = `creation-${e.id}`;
        addNode(sourceId, `Creation (${e.out_lot_name})`, '#d8b4fe'); // Purple
      }

      if (targetId) {
        addNode(targetId, `${e.out_lot_name} (Seq ${e.out_lot_sequence})`, '#f8fafc'); 
      } else {
        targetId = `disposal-${e.id}`;
        addNode(targetId, `Disposal (${e.out_lot_name})`, '#fca5a5'); // Red
      }

      // 2. Generate Edges with Color Logic
      let edgeColor = '#94a3b8'; // Default gray for sequence bumps
      if (e.in_lot_name && e.out_lot_name) {
        if (e.in_lot_name !== searchLot && e.out_lot_name === searchLot) edgeColor = '#10b981'; // Green for incoming merges
        if (e.in_lot_name === searchLot && e.out_lot_name !== searchLot) edgeColor = '#f97316'; // Orange for outgoing splits
      }

      initialEdges.push({
        id: `edge-${e.id}`,
        source: sourceId,
        target: targetId,
        type: 'smoothstep',
        label: (
          <>
            <tspan x="0" dy="-1.2em">Seg ID: {e.segment_uuid}</tspan>
            <tspan x="0" dy="1.2em">Equipment: {e.equipment_path}</tspan>
            <tspan x="0" dy="1.2em">Operator: {e.operator || 'None'}</tspan>
            <tspan x="0" dy="1.2em">Location: {e.location_type}</tspan>
          </>
        ),
        labelStyle: { fill: '#333', fontWeight: 700, fontSize: 11 },
        style: { stroke: edgeColor, strokeWidth: 2 },
        markerEnd: { type: MarkerType.ArrowClosed, color: edgeColor },
        animated: edgeColor !== '#94a3b8', // Animate transformation events
      });
    });

    // 3. Apply Auto-Layout
    const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
      initialNodes,
      initialEdges
    );

    setNodes(layoutedNodes);
    setEdges(layoutedEdges);
  }, [searchLot]); // Removed rfInstance from dependencies if it was there to prevent loop

  // Moved handleResetLayout outside of buildGraph
  const handleResetLayout = () => {
    // 1. Snap nodes back to their original calculated positions
    if (rawEvents.length > 0) {
      buildGraph(rawEvents);
    }
    
    // 2. Wait for React to render the snapped positions before moving the camera
    if (rfInstance) {
      setTimeout(() => {
        rfInstance.fitView({ duration: 800, padding: 0.1 });
      }, 50); // A 50ms delay is plenty of time for the DOM to update
    }
  };

  return (
    // Removed max-w-6xl, added h-full to make the outer container fill the parent
    <div className="flex flex-col w-full h-full p-4 space-y-4">
      <div className="flex w-full space-x-4 mb-2">
        <input
          type="text"
          value={searchLot}
          onChange={(e) => setSearchLot(e.target.value.replace(/[^a-zA-Z0-9]/g, ''))}
          placeholder="Enter Lot Name..."
          className="border border-gray-300 p-2 rounded w-64 shadow-sm"
        />
        <button 
          onClick={handleResetLayout}
          className="px-4 py-2 bg-blue-600 text-white rounded shadow-sm hover:bg-blue-700 transition-colors"
        >
          Reset Layout
        </button>
        {loading && <span className="flex items-center text-sm text-gray-500">Loading...</span>}
      </div>

      {/* Replaced h-[600px] with flex-1 and min-h-0 to dynamically fill remaining vertical space */}
      <div className="bg-white border rounded shadow-sm w-full flex-1 min-h-[500px]">
        {nodes.length > 0 ? (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onInit={setRfInstance} 
            fitView
            attributionPosition="bottom-right"
          >
            <Background color="#ccc" gap={16} />
            <Controls />
          </ReactFlow>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500">
            {loading ? 'Fetching data...' : 'No history found for this lot.'}
          </div>
        )}
      </div>
    </div>
  );
}
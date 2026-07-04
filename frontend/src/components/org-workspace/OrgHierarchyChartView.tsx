"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type Node,
  type OnNodeDrag,
  type XYPosition,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Maximize2,
  Search,
  ZoomIn,
  ZoomOut,
} from "lucide-react";

import {
  employeeFlowNodeTypes,
  type EmployeeFlowNodeData,
} from "@/components/org-workspace/EmployeeFlowNode";
import { AddEmployeeButton } from "@/components/org-workspace/AddEmployeeButton";
import {
  buildEmployeeTree,
  collectLayoutEdges,
  collectLayoutNodes,
  layoutEmployeeTree,
  NODE_WIDTH,
  selectReparentTarget,
  wouldCreateCycle,
} from "@/lib/org-tree-utils";
import type { Employee } from "@/lib/types";

interface OrgHierarchyChartViewProps {
  employees: Employee[];
  selectedIds: Set<string>;
  onToggleSelect: (employeeId: string) => void;
  onReparent: (employeeId: string, managerId: string | null) => void;
  onEditEmployee?: (employee: Employee) => void;
  onAddEmployee?: () => void;
  focusEmployeeId?: string | null;
  onFocusHandled?: () => void;
}

function buildGraphElements(
  employees: Employee[],
  selectedIds: Set<string>,
  dropTargetId: string | null,
  highlightedId: string | null,
  onToggleSelect: (id: string) => void,
  onEditEmployee?: (employee: Employee) => void,
): { nodes: Node<EmployeeFlowNodeData>[]; edges: Edge[] } {
  const tree = buildEmployeeTree(employees);
  const { layouts } = layoutEmployeeTree(tree);
  const layoutNodes = collectLayoutNodes(layouts);
  const layoutEdges = collectLayoutEdges(layouts);

  const nodes: Node<EmployeeFlowNodeData>[] = layoutNodes.map((node) => ({
    id: node.employee.id,
    type: "employee",
    position: { x: node.x, y: node.y },
    draggable: true,
    data: {
      employee: node.employee,
      isSelected: selectedIds.has(node.employee.id),
      isDropTarget: dropTargetId === node.employee.id,
      isHighlighted: highlightedId === node.employee.id,
      onToggleSelect: () => onToggleSelect(node.employee.id),
      onEdit: onEditEmployee
        ? () => onEditEmployee(node.employee)
        : undefined,
    },
  }));

  const edges: Edge[] = layoutEdges.map(({ from, to }) => ({
    id: `${from.employee.id}-${to.employee.id}`,
    source: from.employee.id,
    target: to.employee.id,
    type: "smoothstep",
    animated: false,
    style: { stroke: "#52525b", strokeWidth: 2 },
  }));

  return { nodes, edges };
}

function OrgHierarchyCanvas({
  employees,
  selectedIds,
  onToggleSelect,
  onReparent,
  onEditEmployee,
  onAddEmployee,
  focusEmployeeId,
  onFocusHandled,
}: OrgHierarchyChartViewProps) {
  const { fitView, zoomIn, zoomOut, setCenter, getIntersectingNodes } =
    useReactFlow();
  const [nodes, setNodes] = useState<Node<EmployeeFlowNodeData>[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [dropTargetId, setDropTargetId] = useState<string | null>(null);
  const [highlightedId, setHighlightedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  const dragSnapshot = useRef<Map<string, XYPosition>>(new Map());
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = useCallback((message: string) => {
    setToast(message);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 3200);
  }, []);

  const syncGraph = useCallback(
    (targetDropId: string | null = dropTargetId, targetHighlight: string | null = highlightedId) => {
      const graph = buildGraphElements(
        employees,
        selectedIds,
        targetDropId,
        targetHighlight,
        onToggleSelect,
        onEditEmployee,
      );
      setNodes(graph.nodes);
      setEdges(graph.edges);
    },
    [employees, selectedIds, dropTargetId, highlightedId, onToggleSelect, onEditEmployee],
  );

  useEffect(() => {
    syncGraph();
    requestAnimationFrame(() => {
      fitView({ padding: 0.18, duration: 400 });
    });
  }, [employees, selectedIds, syncGraph, fitView]);

  useEffect(() => {
    if (!focusEmployeeId) return;

    const tree = buildEmployeeTree(employees);
    const { layouts } = layoutEmployeeTree(tree);
    const layoutNode = collectLayoutNodes(layouts).find(
      (node) => node.employee.id === focusEmployeeId,
    );

    if (!layoutNode) {
      onFocusHandled?.();
      return;
    }

    setHighlightedId(focusEmployeeId);
    requestAnimationFrame(() => {
      setCenter(layoutNode.x + NODE_WIDTH / 2, layoutNode.y + 50, {
        zoom: 1.15,
        duration: 500,
      });
      syncGraph(dropTargetId, focusEmployeeId);
    });

    const timer = setTimeout(() => {
      setHighlightedId(null);
      syncGraph(dropTargetId, null);
      onFocusHandled?.();
    }, 2400);

    return () => clearTimeout(timer);
  }, [
    employees,
    focusEmployeeId,
    dropTargetId,
    onFocusHandled,
    setCenter,
    syncGraph,
  ]);

  useEffect(
    () => () => {
      if (toastTimer.current) clearTimeout(toastTimer.current);
    },
    [],
  );

  const onNodeDragStart: OnNodeDrag<Node<EmployeeFlowNodeData>> = useCallback(
    (_, node) => {
      dragSnapshot.current = new Map(
        nodes.map((item) => [item.id, { ...item.position }]),
      );
      setDropTargetId(null);
    },
    [nodes],
  );

  const onNodeDrag: OnNodeDrag<Node<EmployeeFlowNodeData>> = useCallback(
    (_, node) => {
      const intersections = getIntersectingNodes(node).filter(
        (item) => item.id !== node.id,
      );
      const nextTarget = selectReparentTarget(
        employees,
        node.id,
        intersections.map((item) => item.id),
      );
      setDropTargetId(nextTarget);

      setNodes((current) =>
        current.map((item) => ({
          ...item,
          data: {
            ...item.data,
            isDropTarget: item.id === nextTarget,
          },
        })),
      );
    },
    [getIntersectingNodes],
  );

  const onNodeDragStop: OnNodeDrag<Node<EmployeeFlowNodeData>> = useCallback(
    (_, node) => {
      const intersections = getIntersectingNodes(node).filter(
        (item) => item.id !== node.id,
      );
      const targetId = selectReparentTarget(
        employees,
        node.id,
        intersections.map((item) => item.id),
      );

      setDropTargetId(null);

      if (!targetId) {
        syncGraph(null, highlightedId);
        return;
      }

      if (wouldCreateCycle(employees, node.id, targetId)) {
        showToast("Cyclical reporting lines are not allowed");
        setNodes((current) =>
          current.map((item) => ({
            ...item,
            position: dragSnapshot.current.get(item.id) ?? item.position,
            data: { ...item.data, isDropTarget: false },
          })),
        );
        return;
      }

      onReparent(node.id, targetId);
    },
    [employees, getIntersectingNodes, highlightedId, onReparent, showToast, syncGraph],
  );

  function handleSearch() {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return;

    const match = employees.find(
      (employee) =>
        employee.name.toLowerCase().includes(query) ||
        employee.email.toLowerCase().includes(query) ||
        employee.role.toLowerCase().includes(query),
    );

    if (!match) {
      showToast(`No employee found for "${searchQuery.trim()}"`);
      return;
    }

    const tree = buildEmployeeTree(employees);
    const { layouts } = layoutEmployeeTree(tree);
    const layoutNode = collectLayoutNodes(layouts).find(
      (node) => node.employee.id === match.id,
    );

    if (layoutNode) {
      setHighlightedId(match.id);
      setCenter(layoutNode.x + NODE_WIDTH / 2, layoutNode.y + 50, {
        zoom: 1.15,
        duration: 500,
      });
      syncGraph(dropTargetId, match.id);
      setTimeout(() => {
        setHighlightedId(null);
        syncGraph(dropTargetId, null);
      }, 2200);
    }
  }

  const unparentCandidate = useMemo(() => {
    if (selectedIds.size !== 1) return null;
    return [...selectedIds][0] ?? null;
  }, [selectedIds]);

  return (
    <div className="relative overflow-hidden rounded-xl border border-zinc-800 bg-zinc-950/60">
      <div className="flex flex-wrap items-center gap-2 border-b border-zinc-800 bg-zinc-900/70 px-3 py-2">
        <button
          type="button"
          onClick={() => zoomIn({ duration: 200 })}
          className="rounded-lg border border-zinc-700 p-2 text-zinc-300 hover:bg-zinc-800"
          title="Zoom in"
        >
          <ZoomIn className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => zoomOut({ duration: 200 })}
          className="rounded-lg border border-zinc-700 p-2 text-zinc-300 hover:bg-zinc-800"
          title="Zoom out"
        >
          <ZoomOut className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => fitView({ padding: 0.18, duration: 400 })}
          className="rounded-lg border border-zinc-700 p-2 text-zinc-300 hover:bg-zinc-800"
          title="Fit to screen"
        >
          <Maximize2 className="h-4 w-4" />
        </button>

        <div className="flex min-w-[12rem] flex-1 items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5">
          <Search className="h-4 w-4 shrink-0 text-zinc-500" />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSearch();
            }}
            placeholder="Search employee…"
            className="w-full bg-transparent text-sm text-zinc-100 outline-none placeholder:text-zinc-600"
          />
          <button
            type="button"
            onClick={handleSearch}
            className="rounded-md bg-zinc-800 px-2 py-1 text-xs text-zinc-300 hover:bg-zinc-700"
          >
            Find
          </button>
        </div>

        {unparentCandidate && (
          <button
            type="button"
            onClick={() => onReparent(unparentCandidate, null)}
            className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-400 hover:bg-zinc-800"
          >
            Unparent selected
          </button>
        )}

        {onAddEmployee && <AddEmployeeButton onClick={onAddEmployee} />}
      </div>

      <div className="h-[560px]">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={employeeFlowNodeTypes}
          onNodeDragStart={onNodeDragStart}
          onNodeDrag={onNodeDrag}
          onNodeDragStop={onNodeDragStop}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnScroll
          zoomOnScroll
          minZoom={0.25}
          maxZoom={1.8}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={20} size={1} color="#27272a" />
        </ReactFlow>
      </div>

      <p className="border-t border-zinc-800 px-3 py-2 text-xs text-zinc-500">
        Drag a node onto another to re-parent. Double-click a node to edit role and
        reporting details.
      </p>

      {toast && (
        <div className="absolute bottom-14 left-1/2 z-50 -translate-x-1/2 animate-pulse rounded-lg border border-amber-500/40 bg-amber-500/15 px-4 py-2 text-sm text-amber-100 shadow-xl">
          {toast}
        </div>
      )}
    </div>
  );
}

export function OrgHierarchyChartView(props: OrgHierarchyChartViewProps) {
  return (
    <ReactFlowProvider>
      <OrgHierarchyCanvas {...props} />
    </ReactFlowProvider>
  );
}

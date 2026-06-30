import type { Employee } from "./types";

export interface TreeNode {
  employee: Employee;
  children: TreeNode[];
}

export interface FlatRow {
  employee: Employee;
  depth: number;
  hasChildren: boolean;
}

export interface LayoutNode {
  employee: Employee;
  x: number;
  y: number;
  children: LayoutNode[];
}

const NODE_WIDTH = 240;
const LEVEL_HEIGHT = 148;

export function buildEmployeeTree(employees: Employee[]): TreeNode[] {
  const knownIds = new Set(employees.map((employee) => employee.id));
  const childrenMap = new Map<string, Employee[]>();
  const roots: Employee[] = [];

  for (const employee of employees) {
    if (!employee.manager_id || !knownIds.has(employee.manager_id)) {
      roots.push(employee);
      continue;
    }
    const siblings = childrenMap.get(employee.manager_id) ?? [];
    siblings.push(employee);
    childrenMap.set(employee.manager_id, siblings);
  }

  function toNode(employee: Employee): TreeNode {
    return {
      employee,
      children: (childrenMap.get(employee.id) ?? [])
        .sort((a, b) => a.name.localeCompare(b.name))
        .map(toNode),
    };
  }

  return roots.sort((a, b) => a.name.localeCompare(b.name)).map(toNode);
}

export function wouldCreateCycle(
  employees: Employee[],
  employeeId: string,
  newManagerId: string | null,
): boolean {
  if (employeeId === newManagerId) return true;
  if (!newManagerId) return false;

  let current: string | null = newManagerId;
  while (current) {
    if (current === employeeId) return true;
    const manager = employees.find((employee) => employee.id === current);
    current = manager?.manager_id ?? null;
  }
  return false;
}

export function flattenTree(
  nodes: TreeNode[],
  collapsed: Set<string>,
  depth = 0,
): FlatRow[] {
  const rows: FlatRow[] = [];

  for (const node of nodes) {
    const hasChildren = node.children.length > 0;
    rows.push({ employee: node.employee, depth, hasChildren });
    if (hasChildren && !collapsed.has(node.employee.id)) {
      rows.push(...flattenTree(node.children, collapsed, depth + 1));
    }
  }

  return rows;
}

function measureWidth(node: TreeNode): number {
  if (node.children.length === 0) return 1;
  return node.children.reduce((sum, child) => sum + measureWidth(child), 0);
}

function assignPositions(
  node: TreeNode,
  leftUnits: number,
  depth: number,
): LayoutNode {
  const widthUnits = measureWidth(node);
  const x = (leftUnits + widthUnits / 2) * NODE_WIDTH - NODE_WIDTH / 2;
  const y = depth * LEVEL_HEIGHT;

  let childLeft = leftUnits;
  const children = node.children.map((child) => {
    const childWidth = measureWidth(child);
    const layout = assignPositions(child, childLeft, depth + 1);
    childLeft += childWidth;
    return layout;
  });

  return { employee: node.employee, x, y, children };
}

export function layoutEmployeeTree(nodes: TreeNode[]): {
  layouts: LayoutNode[];
  width: number;
  height: number;
} {
  let offset = 0;
  const layouts: LayoutNode[] = [];

  for (const node of nodes) {
    layouts.push(assignPositions(node, offset, 0));
    offset += measureWidth(node);
  }

  const width = Math.max(offset * NODE_WIDTH, NODE_WIDTH);
  const maxDepth = getMaxDepth(layouts);
  const height = (maxDepth + 1) * LEVEL_HEIGHT + 80;

  return { layouts, width, height };
}

function getMaxDepth(nodes: LayoutNode[], depth = 0): number {
  return nodes.reduce((max, node) => {
    if (node.children.length === 0) return Math.max(max, depth);
    return Math.max(max, getMaxDepth(node.children, depth + 1));
  }, depth);
}

export function collectLayoutNodes(nodes: LayoutNode[]): LayoutNode[] {
  const collected: LayoutNode[] = [];
  for (const node of nodes) {
    collected.push(node);
    collected.push(...collectLayoutNodes(node.children));
  }
  return collected;
}

export function collectLayoutEdges(nodes: LayoutNode[]): Array<{
  from: LayoutNode;
  to: LayoutNode;
}> {
  const edges: Array<{ from: LayoutNode; to: LayoutNode }> = [];
  for (const node of nodes) {
    for (const child of node.children) {
      edges.push({ from: node, to: child });
      edges.push(...collectLayoutEdges([child]));
    }
  }
  return edges;
}

export { NODE_WIDTH, LEVEL_HEIGHT };

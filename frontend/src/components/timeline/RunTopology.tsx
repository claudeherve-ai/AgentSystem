import { useLayoutEffect, useRef, useState } from "react";
import type { TopologyModel, TopologyNode } from "./deriveTopology";
import styles from "./RunTopology.module.css";

interface RunTopologyProps {
  model: TopologyModel;
}

const KIND_LABEL: Record<TopologyNode["kind"], string> = {
  planner: "Planner",
  agent: "Agent",
  tool: "Tool call",
  approval: "Approval",
  artifact: "Artifact",
  output: "Output",
};

const STATUS_LABEL: Record<TopologyNode["status"], string> = {
  pending: "Pending",
  active: "Active",
  done: "Done",
  blocked: "Awaiting approval",
  failed: "Failed",
  cancelled: "Cancelled",
};

interface EdgePath {
  id: string;
  d: string;
}

/**
 * The "memorable" live element: a real, screen-reader-navigable ordered
 * list of every planner/agent/tool/approval/artifact node touched by a run,
 * with a decorative SVG connector overlay drawn between actual DOM node
 * positions. The list itself (not the SVG) is the source of truth for
 * structure and status, so the component degrades gracefully without
 * JavaScript-measured layout and remains fully usable with assistive tech.
 */
export function RunTopology({ model }: RunTopologyProps) {
  const railRef = useRef<HTMLOListElement>(null);
  const nodeRefs = useRef(new Map<string, HTMLLIElement>());
  const [paths, setPaths] = useState<EdgePath[]>([]);

  const setNodeRef = (id: string) => (el: HTMLLIElement | null) => {
    if (el) nodeRefs.current.set(id, el);
    else nodeRefs.current.delete(id);
  };

  useLayoutEffect(() => {
    const rail = railRef.current;
    if (!rail) return;

    const compute = () => {
      const railBox = rail.getBoundingClientRect();
      const next: EdgePath[] = [];
      for (const edge of model.edges) {
        const fromEl = nodeRefs.current.get(edge.from);
        const toEl = nodeRefs.current.get(edge.to);
        if (!fromEl || !toEl) continue;
        const fromBox = fromEl.getBoundingClientRect();
        const toBox = toEl.getBoundingClientRect();
        const x1 = fromBox.right - railBox.left + rail.scrollLeft;
        const y1 = fromBox.top + fromBox.height / 2 - railBox.top;
        const x2 = toBox.left - railBox.left + rail.scrollLeft;
        const y2 = toBox.top + toBox.height / 2 - railBox.top;
        const midX = (x1 + x2) / 2;
        next.push({
          id: `${edge.from}=>${edge.to}`,
          d: `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`,
        });
      }
      setPaths(next);
    };

    compute();
    const observer = new ResizeObserver(compute);
    observer.observe(rail);
    window.addEventListener("resize", compute);
    rail.addEventListener("scroll", compute, { passive: true });
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", compute);
      rail.removeEventListener("scroll", compute);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [model.nodes, model.edges]);

  if (model.nodes.length === 0) {
    return (
      <p className={styles.empty}>
        No run activity yet. Once a task starts, the planner, agents, tools, approvals, and
        artifacts it touches will appear here in order.
      </p>
    );
  }

  return (
    <div className={styles.wrapper}>
      <svg className={styles.edges} aria-hidden="true">
        {paths.map((p) => (
          <path key={p.id} d={p.d} className={styles.edgePath} />
        ))}
      </svg>
      <ol
        ref={railRef}
        className={styles.rail}
        aria-label="Run topology: planner, agents, tools, approvals, and artifacts in order"
      >
        {model.nodes.map((node) => (
          <li
            key={node.id}
            ref={setNodeRef(node.id)}
            className={[styles.node, styles[`kind-${node.kind}`], styles[`status-${node.status}`]]
              .filter(Boolean)
              .join(" ")}
          >
            <span className={styles.kind}>{KIND_LABEL[node.kind]}</span>
            <span className={styles.label}>{node.label}</span>
            {node.detail ? <span className={styles.detail}>{node.detail}</span> : null}
            <span className={styles.statusPill}>{STATUS_LABEL[node.status]}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

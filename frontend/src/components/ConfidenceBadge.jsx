import React from "react";

/**
 * Renders a premium, micro-animated badge indicating confidence level (high/medium/low).
 */
export default function ConfidenceBadge({ confidence }) {
  const normalized = String(confidence).toLowerCase();

  let styles = {
    bg: "bg-emerald-500/10 border-emerald-500/30 text-emerald-400",
    dot: "bg-emerald-500",
    label: "High"
  };

  if (normalized === "medium") {
    styles = {
      bg: "bg-amber-500/10 border-amber-500/30 text-amber-400",
      dot: "bg-amber-500",
      label: "Medium"
    };
  } else if (normalized === "low") {
    styles = {
      bg: "bg-rose-500/10 border-rose-500/30 text-rose-400 animate-pulse",
      dot: "bg-rose-500",
      label: "Low"
    };
  }

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border ${styles.bg}`}>
      <span className={`w-1.5 h-1.5 rounded-full mr-1.5 ${styles.dot}`}></span>
      {styles.label}
    </span>
  );
}

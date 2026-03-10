import React from "react";

/**
 * DocumentationPanel — renders the LLM-generated documentation (Markdown-ish).
 */
export default function DocumentationPanel({ content = "" }) {
  if (!content) {
    return (
      <div className="card">
        <h2>Documentation</h2>
        <p style={{ color: "var(--text-secondary)" }}>
          No documentation generated yet.
        </p>
      </div>
    );
  }

  return (
    <div className="card">
      <h2>Documentation</h2>
      <div className="doc-panel">{content}</div>
    </div>
  );
}

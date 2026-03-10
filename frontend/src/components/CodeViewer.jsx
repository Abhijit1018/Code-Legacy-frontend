import React from "react";
import Editor from "@monaco-editor/react";

/**
 * CodeViewer — displays source code in a Monaco editor (read-only).
 *
 * Props:
 *   code       — string of source code to display
 *   language   — Monaco language id (e.g. "python", "go", "cobol")
 *   title      — optional heading shown above the editor
 *   height     — CSS height (default: 400px)
 */
export default function CodeViewer({
  code = "",
  language = "plaintext",
  title = "",
  height = "400px",
}) {
  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      {title && (
        <div
          style={{
            padding: "0.6rem 1rem",
            borderBottom: "1px solid var(--border)",
            fontSize: "0.85rem",
            fontWeight: 600,
            color: "var(--text-secondary)",
          }}
        >
          {title}
        </div>
      )}
      <Editor
        height={height}
        language={language}
        value={code}
        theme="vs-dark"
        options={{
          readOnly: true,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          fontSize: 13,
          fontFamily: "var(--font-mono)",
          wordWrap: "on",
          padding: { top: 12 },
        }}
      />
    </div>
  );
}

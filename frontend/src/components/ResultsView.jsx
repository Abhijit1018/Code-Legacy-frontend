import React, { useState } from "react";
import CodeViewer from "./CodeViewer";
import DocumentationPanel from "./DocumentationPanel";
import OriginalCodeViewer from "./OriginalCodeViewer";

/**
 * ResultsView — tabbed display of analysis results.
 *
 * Tabs: Summary | Original Code | Python | Go | Documentation
 *
 * Props:
 *   data — the full ModernizationResponse object from the API
 */
export default function ResultsView({ data }) {
  const [tab, setTab] = useState("summary");
  const [selectedFileIdx, setSelectedFileIdx] = useState(0);

  if (!data) return null;

  const { stats, results, llm } = data;
  const perFile = results.per_file_results || [];
  const hasPerFile = perFile.length > 0;
  const selectedFile = hasPerFile ? perFile[selectedFileIdx] : null;

  const tabs = [
    { id: "summary", label: "Summary" },
    { id: "original", label: "Original Code" },
    { id: "python", label: "Python" },
    { id: "go", label: "Go" },
    { id: "docs", label: "Documentation" },
  ];

  return (
    <div>
      {/* ---- Stats row ---- */}
      <div className="stats-row">
        <span className="stat-badge">
          Files <span className="value">{stats.files_scanned}</span>
        </span>
        <span className="stat-badge">
          Functions <span className="value">{stats.functions_found}</span>
        </span>
        <span className="stat-badge">
          Languages{" "}
          <span className="value">
            {stats.languages_detected.join(", ") || "—"}
          </span>
        </span>
        <span className="stat-badge">
          Compression saved{" "}
          <span className="value">{stats.compression_savings_percent}%</span>
        </span>
        <span className="stat-badge">
          Model <span className="value">{llm.model_used || "—"}</span>
        </span>
        <span className="stat-badge">
          Tokens <span className="value">{llm.tokens_used}</span>
        </span>
      </div>

      {/* ---- File selector (only when per-file results exist) ---- */}
      {hasPerFile && (
        <div className="file-selector" style={{
          display: "flex",
          alignItems: "center",
          gap: "0.75rem",
          margin: "1rem 0",
          padding: "0.75rem 1rem",
          background: "rgba(255,255,255,0.05)",
          borderRadius: "8px",
          border: "1px solid rgba(255,255,255,0.1)",
        }}>
          <label style={{ fontWeight: 600, fontSize: "0.9rem", color: "#a7b4c6" }}>
            File:
          </label>
          <select
            value={selectedFileIdx}
            onChange={(e) => setSelectedFileIdx(Number(e.target.value))}
            style={{
              flex: 1,
              padding: "0.5rem 0.75rem",
              borderRadius: "6px",
              border: "1px solid rgba(255,255,255,0.2)",
              background: "rgba(0,0,0,0.3)",
              color: "#e0e6ed",
              fontSize: "0.9rem",
              cursor: "pointer",
            }}
          >
            {perFile.map((f, idx) => (
              <option key={idx} value={idx}>
                {f.program_id || f.file_path}
                {f.error ? " ⚠️ (error)" : ""}
              </option>
            ))}
          </select>
          <span style={{
            fontSize: "0.8rem",
            color: "#8899aa",
          }}>
            {perFile.length} file{perFile.length !== 1 ? "s" : ""} detected
          </span>
        </div>
      )}

      {/* ---- Tabs ---- */}
      <div className="tabs">
        {tabs.map((t) => (
          <button
            key={t.id}
            className={`tab ${tab === t.id ? "active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ---- Tab panels ---- */}
      {tab === "summary" && (
        <div className="card">
          <h2>Summary</h2>
          {hasPerFile && selectedFile ? (
            <>
              <h3 style={{ color: "#7c8cf8", marginBottom: "0.5rem" }}>
                {selectedFile.program_id || selectedFile.file_path}
              </h3>
              <p style={{ whiteSpace: "pre-wrap" }}>
                {selectedFile.summary || "No summary."}
              </p>
              {selectedFile.error && (
                <p style={{ color: "#ff6b6b", marginTop: "0.5rem" }}>
                  ⚠️ Error: {selectedFile.error}
                </p>
              )}
            </>
          ) : (
            <p style={{ whiteSpace: "pre-wrap" }}>
              {results.summary || "No summary."}
            </p>
          )}
          {results.dependency_explanation && (
            <>
              <h2 style={{ marginTop: "1rem" }}>Dependencies</h2>
              <p style={{ whiteSpace: "pre-wrap" }}>
                {results.dependency_explanation}
              </p>
            </>
          )}
        </div>
      )}

      {tab === "original" && (
        <OriginalCodeViewer originalCode={results.original_code} />
      )}

      {tab === "python" && (
        <CodeViewer
          code={hasPerFile && selectedFile ? selectedFile.python_code : results.python_code}
          language="python"
          title={
            hasPerFile && selectedFile
              ? `Generated Python — ${selectedFile.program_id || selectedFile.file_path}`
              : "Generated Python"
          }
        />
      )}

      {tab === "go" && (
        <CodeViewer
          code={hasPerFile && selectedFile ? selectedFile.go_code : results.go_code}
          language="go"
          title={
            hasPerFile && selectedFile
              ? `Generated Go — ${selectedFile.program_id || selectedFile.file_path}`
              : "Generated Go"
          }
        />
      )}

      {tab === "docs" && (
        <DocumentationPanel
          content={
            hasPerFile && selectedFile
              ? selectedFile.documentation
              : results.documentation
          }
        />
      )}
    </div>
  );
}

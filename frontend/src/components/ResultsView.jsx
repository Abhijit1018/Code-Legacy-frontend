import React, { useState } from "react";
import DocumentationPanel from "./DocumentationPanel";

/**
 * TerminalTile — a single terminal-style code viewer.
 */
function TerminalTile({ title, language, code, langClass }) {
  if (!code) {
    return (
      <div className="terminal-tile">
        <div className="terminal-header">
          <div className="terminal-dots">
            <span className="dot-red" />
            <span className="dot-yellow" />
            <span className="dot-green" />
          </div>
          <span className="terminal-title">{title}</span>
          <span className={`terminal-lang-badge ${langClass}`}>{language}</span>
        </div>
        <div className="terminal-empty">No code available</div>
      </div>
    );
  }

  const lines = code.split("\n");

  return (
    <div className="terminal-tile">
      <div className="terminal-header">
        <div className="terminal-dots">
          <span className="dot-red" />
          <span className="dot-yellow" />
          <span className="dot-green" />
        </div>
        <span className="terminal-title">{title}</span>
        <span className={`terminal-lang-badge ${langClass}`}>{language}</span>
      </div>
      <div className="terminal-body">
        <pre>
          <div className="line-numbers">
            <div className="line-nums">
              {lines.map((_, i) => (
                <div key={i}>{i + 1}</div>
              ))}
            </div>
            <div className="line-content">
              {lines.map((line, i) => (
                <div key={i}>{line || " "}</div>
              ))}
            </div>
          </div>
        </pre>
      </div>
    </div>
  );
}

/**
 * ValidationBadge — shows pass/fail status for validation.
 */
function ValidationBadge({ validation }) {
  if (!validation) return <span className="val-badge val-skip">⏭ Skipped</span>;
  if (validation.passed) return <span className="val-badge val-pass">✅ Passed</span>;
  return <span className="val-badge val-fail">❌ Failed ({validation.errors?.length || 0} errors)</span>;
}

/**
 * ResultsView — displays analysis results with tabs:
 *  • Code — side-by-side code comparison (original + translated)
 *  • Architecture — repo philosophy & dependency graph
 *  • File Map — mapping of original → modernised file paths
 *  • Workflows — detected & converted workflow artifacts
 *  • Documentation — generated docs
 *  • Validation — per-file validation report
 *
 * Props:
 *   data — the full ModernizationResponse object from the API
 */
export default function ResultsView({ data }) {
  const [selectedFileIdx, setSelectedFileIdx] = useState(0);
  const [activeTab, setActiveTab] = useState("code");

  if (!data) return null;

  const { stats, results, llm } = data;
  const perFile = results.per_file_results || [];
  const hasPerFile = perFile.length > 0;
  const selectedFile = hasPerFile ? perFile[selectedFileIdx] : null;

  // Get Phase 1/2/3 outputs
  const repoPhilosophy = data.repo_philosophy || {};
  const dependencyGraph = data.dependency_graph || {};
  const fileMapping = data.file_mapping || {};
  const validationReport = data.validation_report || [];
  const workflows = data.workflows || [];

  // Code data
  const summaryText = hasPerFile && selectedFile ? selectedFile.summary : results.summary;
  const originalCode = hasPerFile && selectedFile
    ? selectedFile.original_code
    : results.original_code
      ? Object.values(results.original_code).join("\n\n")
      : "";
  const pythonCode = hasPerFile && selectedFile ? selectedFile.python_code : results.python_code;
  const goCode = hasPerFile && selectedFile ? selectedFile.go_code : results.go_code;
  const documentation = hasPerFile && selectedFile ? selectedFile.documentation : results.documentation;
  const cobolFileName = hasPerFile && selectedFile
    ? selectedFile.file_path || selectedFile.program_id || "source.cbl"
    : "original.cbl";
  const pythonFileName = hasPerFile && selectedFile
    ? `${(selectedFile.program_id || "output").toLowerCase()}.py`
    : "output.py";

  const tabs = [
    { key: "code", label: "💻 Code", show: true },
    { key: "architecture", label: "🏗️ Architecture", show: Object.keys(repoPhilosophy).length > 0 },
    { key: "filemap", label: "🗂️ File Map", show: Object.keys(fileMapping).length > 0 },
    { key: "workflows", label: "⚙️ Workflows", show: workflows.length > 0 },
    { key: "docs", label: "📖 Documentation", show: !!documentation },
    { key: "validation", label: "✅ Validation", show: validationReport.length > 0 },
  ].filter((t) => t.show);

  return (
    <div id="results-view">
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
          <span className="value">{stats.languages_detected.join(", ") || "—"}</span>
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

      {/* ---- Summary ---- */}
      <div className="summary-card">
        <h2>
          📋 {hasPerFile && selectedFile
            ? selectedFile.program_id || selectedFile.file_path
            : "Analysis Summary"}
        </h2>
        <div className="summary-text">{summaryText || "No summary available."}</div>
        {selectedFile && selectedFile.error && (
          <p style={{ color: "var(--danger)", marginTop: "0.75rem" }}>
            ⚠️ Error: {selectedFile.error}
          </p>
        )}
        {results.dependency_explanation && (
          <div className="dependency-section">
            <h3>Dependencies & Translation Order</h3>
            <div className="summary-text">{results.dependency_explanation}</div>
          </div>
        )}
      </div>

      {/* ---- Tab bar ---- */}
      <div className="results-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            id={`tab-${tab.key}`}
            className={`results-tab ${activeTab === tab.key ? "active" : ""}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ---- CODE TAB ---- */}
      {activeTab === "code" && (
        <>
          {/* File dropdown */}
          {hasPerFile && perFile.length > 0 && (
            <div className="file-dropdown-bar">
              <label htmlFor="file-select">📁 Select File:</label>
              <select
                id="file-select"
                value={selectedFileIdx}
                onChange={(e) => setSelectedFileIdx(Number(e.target.value))}
              >
                {perFile.map((f, idx) => (
                  <option key={idx} value={idx}>
                    {f.program_id || f.file_path}
                    {f.error ? " ⚠️ (error)" : ""}
                    {f.validation ? (f.validation.passed ? " ✅" : " ❌") : ""}
                  </option>
                ))}
              </select>
              <span className="file-count">
                {perFile.length} file{perFile.length !== 1 ? "s" : ""} detected
              </span>
              {selectedFile?.validation && (
                <ValidationBadge validation={selectedFile.validation} />
              )}
            </div>
          )}

          {/* Side-by-side terminals */}
          <div className="code-comparison">
            <TerminalTile title={cobolFileName} language="COBOL" langClass="cobol" code={originalCode} />
            <TerminalTile title={pythonFileName} language="Python" langClass="python" code={pythonCode} />
          </div>

          {/* Go code (if available) */}
          {goCode && (
            <div className="code-comparison" style={{ gridTemplateColumns: "1fr" }}>
              <TerminalTile
                title={hasPerFile && selectedFile
                  ? `${(selectedFile.program_id || "output").toLowerCase()}.go`
                  : "output.go"
                }
                language="Go"
                langClass="python"
                code={goCode}
              />
            </div>
          )}
        </>
      )}

      {/* ---- ARCHITECTURE TAB ---- */}
      {activeTab === "architecture" && (
        <div className="tab-panel architecture-panel">
          <h3>🏗️ Repository Architecture</h3>
          <div className="philosophy-grid">
            {repoPhilosophy.architectural_pattern && (
              <div className="philosophy-card">
                <span className="philosophy-label">Pattern</span>
                <span className="philosophy-value">{repoPhilosophy.architectural_pattern}</span>
              </div>
            )}
            {repoPhilosophy.primary_data_flow && (
              <div className="philosophy-card">
                <span className="philosophy-label">Data Flow</span>
                <span className="philosophy-value">{repoPhilosophy.primary_data_flow}</span>
              </div>
            )}
            {repoPhilosophy.configuration_strategy && (
              <div className="philosophy-card">
                <span className="philosophy-label">Configuration</span>
                <span className="philosophy-value">{repoPhilosophy.configuration_strategy}</span>
              </div>
            )}
            {repoPhilosophy.error_handling_philosophy && (
              <div className="philosophy-card">
                <span className="philosophy-label">Error Handling</span>
                <span className="philosophy-value">{repoPhilosophy.error_handling_philosophy}</span>
              </div>
            )}
            {repoPhilosophy.execution_order && (
              <div className="philosophy-card">
                <span className="philosophy-label">Execution Order</span>
                <span className="philosophy-value">{repoPhilosophy.execution_order}</span>
              </div>
            )}
          </div>
          {repoPhilosophy.entry_points?.length > 0 && (
            <div className="entry-points">
              <h4>Entry Points</h4>
              <div className="entry-points-list">
                {repoPhilosophy.entry_points.map((ep, i) => (
                  <span key={i} className="entry-point-badge">{ep}</span>
                ))}
              </div>
            </div>
          )}
          {repoPhilosophy.domain_patterns?.length > 0 && (
            <div className="domain-patterns">
              <h4>Domain Patterns</h4>
              <ul>{repoPhilosophy.domain_patterns.map((dp, i) => <li key={i}>{dp}</li>)}</ul>
            </div>
          )}

          {/* Dependency graph summary */}
          {Object.keys(dependencyGraph).length > 0 && (
            <div className="dep-graph-section">
              <h4>Dependency Graph</h4>
              <div className="dep-graph-stats">
                <span className="stat-badge">Files <span className="value">{Object.keys(dependencyGraph).length}</span></span>
                <span className="stat-badge">
                  Edges <span className="value">
                    {Object.values(dependencyGraph).reduce((sum, n) => sum + (n.edges?.length || 0), 0)}
                  </span>
                </span>
              </div>
              <div className="dep-graph-list">
                {Object.entries(dependencyGraph).map(([file, info]) => (
                  <div key={file} className="dep-graph-node">
                    <code>{file}</code>
                    <span className="dep-lang">{info.language}</span>
                    {info.edges?.length > 0 && (
                      <span className="dep-edges">
                        → {info.edges.map((e) => e.target).join(", ")}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ---- FILE MAP TAB ---- */}
      {activeTab === "filemap" && (
        <div className="tab-panel filemap-panel">
          <h3>🗂️ File Mapping</h3>
          <p className="tab-description">How original files map to the modernised project structure.</p>
          <div className="filemap-table">
            <div className="filemap-header">
              <span>Original</span>
              <span>→</span>
              <span>Modernised</span>
            </div>
            {Object.entries(fileMapping).map(([orig, modern]) => (
              <div key={orig} className="filemap-row">
                <code className="filemap-orig">{orig}</code>
                <span className="filemap-arrow">→</span>
                <code className="filemap-modern">{modern}</code>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ---- WORKFLOWS TAB ---- */}
      {activeTab === "workflows" && (
        <div className="tab-panel workflows-panel">
          <h3>⚙️ Detected Workflows</h3>
          <p className="tab-description">Legacy workflow artifacts detected and converted.</p>
          {workflows.map((wf, i) => (
            <div key={i} className="workflow-card">
              <div className="workflow-header">
                <span className="workflow-type-badge">{wf.workflow_type}</span>
                <span className="workflow-description">{wf.description}</span>
              </div>
              <div className="workflow-details">
                <div><strong>Source:</strong> <code>{wf.source_file}</code></div>
                <div><strong>Output:</strong> <code>{wf.modern_file_path}</code></div>
              </div>
              {wf.modern_content && (
                <details className="workflow-content">
                  <summary>View generated content</summary>
                  <pre>{wf.modern_content}</pre>
                </details>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ---- DOCUMENTATION TAB ---- */}
      {activeTab === "docs" && (
        <div className="tab-panel">
          <DocumentationPanel content={documentation} />
        </div>
      )}

      {/* ---- VALIDATION TAB ---- */}
      {activeTab === "validation" && (
        <div className="tab-panel validation-panel">
          <h3>✅ Validation Report</h3>
          <div className="validation-summary">
            <span className="stat-badge">
              Passed <span className="value">{validationReport.filter((v) => v.passed).length}</span>
            </span>
            <span className="stat-badge">
              Failed <span className="value">{validationReport.filter((v) => !v.passed).length}</span>
            </span>
            <span className="stat-badge">
              Total <span className="value">{validationReport.length}</span>
            </span>
          </div>
          <div className="validation-list">
            {validationReport.map((v, i) => (
              <div key={i} className={`validation-row ${v.passed ? "val-row-pass" : "val-row-fail"}`}>
                <div className="validation-row-header">
                  <code>{v.file_path}</code>
                  <span className="val-target">{v.target_language}</span>
                  <ValidationBadge validation={v} />
                  {v.retry_count > 0 && <span className="val-retry">🔄 {v.retry_count} retries</span>}
                </div>
                {v.errors?.length > 0 && (
                  <ul className="validation-errors">
                    {v.errors.map((err, j) => <li key={j}>{err}</li>)}
                  </ul>
                )}
                {v.warnings?.length > 0 && (
                  <ul className="validation-warnings">
                    {v.warnings.map((w, j) => <li key={j}>{w}</li>)}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

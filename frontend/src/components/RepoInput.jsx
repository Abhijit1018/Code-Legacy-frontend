import React, { useState } from "react";

const LLM_MODELS = [
  { value: "nvidia/nemotron-3-super-120b-a12b:free", label: "NVIDIA Nemotron 3 120B (FREE)" },
  { value: "z-ai/glm-4.5-air:free", label: "GLM 4.5 Air (FREE)" },
  { value: "meta-llama/llama-3.3-70b-instruct:free", label: "Llama 3.3 70B (FREE - Best)" },
  { value: "qwen/qwen-2.5-72b-instruct:free", label: "Qwen 2.5 72B (FREE)" },
  { value: "google/gemini-2.0-flash-exp:free", label: "Gemini 2.0 Flash (Check status)" },
  { value: "deepseek/deepseek-chat", label: "DeepSeek Chat (Paid)" },
  { value: "openai/gpt-4o", label: "GPT-4o (Paid)" },
  { value: "anthropic/claude-3.5-sonnet", label: "Claude 3.5 Sonnet (Paid)" },
];

/**
 * RepoInput — form for entering a GitHub repository URL plus options.
 *
 * Props:
 *   onSubmit(repoUrl, branch, targetLanguage, options) — called when the user clicks Analyse
 *   loading — disables the button while processing
 */
export default function RepoInput({ onSubmit, loading = false }) {
  const [repoUrl, setRepoUrl] = useState("");
  const [branch, setBranch] = useState("main");
  const [targetLanguage, setTargetLanguage] = useState("python");
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [compressionRate, setCompressionRate] = useState(0.5);
  const [llmModel, setLlmModel] = useState("nvidia/nemotron-3-super-120b-a12b:free");
  const [temperature, setTemperature] = useState(0.2);
  const [maxTokens, setMaxTokens] = useState(4096);
  const [removeComments, setRemoveComments] = useState(true);
  const [removeTests, setRemoveTests] = useState(true);
  const [githubToken, setGithubToken] = useState("");
  const [additionalInstructions, setAdditionalInstructions] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (repoUrl.trim()) {
      onSubmit(repoUrl.trim(), branch.trim(), targetLanguage, {
        compressionRate,
        llmModel,
        temperature,
        maxTokens,
        removeComments,
        removeTests,
        githubToken: githubToken.trim(),
        additionalInstructions: additionalInstructions.trim(),
      });
    }
  };

  return (
    <form className="card" onSubmit={handleSubmit}>
      <h2>Analyse Legacy Repository</h2>

      <div className="input-group">
        <input
          type="url"
          placeholder="https://github.com/owner/repo"
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          required
        />
        <input
          type="text"
          placeholder="Branch"
          value={branch}
          onChange={(e) => setBranch(e.target.value)}
          style={{ maxWidth: 140 }}
        />
      </div>

      <div className="input-group">
        <label style={{ fontWeight: 500, marginRight: 8 }}>Convert to:</label>
        <select
          value={targetLanguage}
          onChange={(e) => setTargetLanguage(e.target.value)}
        >
          <option value="python">Python</option>
          <option value="go">Go</option>
        </select>

        <button
          className="btn btn-primary"
          type="submit"
          disabled={loading || !repoUrl.trim()}
        >
          {loading ? "Analysing…" : "Analyse"}
        </button>
      </div>

      {/* Advanced Options Toggle */}
      <button
        type="button"
        className="btn-link"
        onClick={() => setShowAdvanced(!showAdvanced)}
        style={{
          background: "none",
          border: "none",
          color: "var(--accent, #4f8cff)",
          cursor: "pointer",
          padding: "0.5rem 0",
          fontSize: "0.9rem",
          textDecoration: "underline",
        }}
      >
        {showAdvanced ? "▾ Hide Advanced Options" : "▸ Show Advanced Options"}
      </button>

      {showAdvanced && (
        <div
          className="advanced-options"
          style={{ display: "grid", gap: "0.75rem", marginTop: "0.5rem" }}
        >
          {/* LLM Model */}
          <div className="input-group" style={{ alignItems: "center" }}>
            <label style={{ minWidth: 150, fontWeight: 500 }}>LLM Model:</label>
            <select
              value={llmModel}
              onChange={(e) => setLlmModel(e.target.value)}
              style={{ flex: 1 }}
            >
              {LLM_MODELS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>

          {/* Temperature */}
          <div className="input-group" style={{ alignItems: "center" }}>
            <label style={{ minWidth: 150, fontWeight: 500 }}>
              Temperature: {temperature}
            </label>
            <input
              type="range"
              min="0"
              max="2"
              step="0.1"
              value={temperature}
              onChange={(e) => setTemperature(parseFloat(e.target.value))}
              style={{ flex: 1 }}
            />
          </div>

          {/* Max Tokens */}
          <div className="input-group" style={{ alignItems: "center" }}>
            <label style={{ minWidth: 150, fontWeight: 500 }}>
              Max Tokens:
            </label>
            <select
              value={maxTokens}
              onChange={(e) => setMaxTokens(parseInt(e.target.value))}
            >
              <option value={2048}>2,048</option>
              <option value={4096}>4,096 (default)</option>
              <option value={8192}>8,192</option>
              <option value={16384}>16,384</option>
              <option value={32768}>32,768</option>
            </select>
          </div>

          {/* Compression Rate */}
          <div className="input-group" style={{ alignItems: "center" }}>
            <label style={{ minWidth: 150, fontWeight: 500 }}>
              Compression: {compressionRate}
            </label>
            <input
              type="range"
              min="0.1"
              max="1.0"
              step="0.1"
              value={compressionRate}
              onChange={(e) => setCompressionRate(parseFloat(e.target.value))}
              style={{ flex: 1 }}
            />
          </div>

          {/* Toggles */}
          <div className="input-group" style={{ gap: "1.5rem" }}>
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={removeComments}
                onChange={(e) => setRemoveComments(e.target.checked)}
              />
              Strip Comments
            </label>
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={removeTests}
                onChange={(e) => setRemoveTests(e.target.checked)}
              />
              Exclude Tests
            </label>
          </div>

          {/* GitHub Token */}
          <div className="input-group" style={{ alignItems: "center" }}>
            <label style={{ minWidth: 150, fontWeight: 500 }}>
              GitHub Token:
            </label>
            <input
              type="password"
              placeholder="For private repos (optional)"
              value={githubToken}
              onChange={(e) => setGithubToken(e.target.value)}
              style={{ flex: 1 }}
            />
          </div>

          {/* Additional Instructions */}
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label style={{ fontWeight: 500 }}>Additional Instructions:</label>
            <textarea
              placeholder="E.g. Use FastAPI framework, follow PEP 8, add type hints…"
              value={additionalInstructions}
              onChange={(e) => setAdditionalInstructions(e.target.value)}
              rows={3}
              style={{
                resize: "vertical",
                padding: "0.5rem",
                borderRadius: 6,
                border: "1px solid var(--border, #ddd)",
              }}
            />
          </div>
        </div>
      )}
    </form>
  );
}

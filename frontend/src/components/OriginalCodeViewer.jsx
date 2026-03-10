import React, { useState } from "react";
import CodeViewer from "./CodeViewer";

/**
 * OriginalCodeViewer — handles displaying the original_code object.
 *
 * Provides a secondary sidebar or tab list to switch between
 * the original legacy files.
 */
export default function OriginalCodeViewer({ originalCode }) {
    if (!originalCode || Object.keys(originalCode).length === 0) {
        return (
            <div className="card">
                <p>No original code context was preserved.</p>
            </div>
        );
    }

    const files = Object.keys(originalCode);
    const [selectedFile, setSelectedFile] = useState(files[0]);

    // Try to guess a language based on file extension
    const guessLanguage = (filename) => {
        const parts = filename.split(".");
        if (parts.length < 2) return "text";
        const ext = parts[parts.length - 1].toLowerCase();
        switch (ext) {
            case "py": return "python";
            case "go": return "go";
            case "js":
            case "jsx": return "javascript";
            case "ts":
            case "tsx": return "typescript";
            case "cbl":
            case "cob": return "cobol";
            case "java": return "java";
            default: return "text";
        }
    };

    return (
        <div className="original-code-container" style={{ display: "flex", gap: "1rem" }}>
            <div className="file-list" style={{ minWidth: 200, display: "flex", flexDirection: "column", gap: 4 }}>
                <h3 style={{ marginTop: 0, marginBottom: "0.5rem", fontSize: "1rem" }}>Original Files</h3>
                {files.map((file) => (
                    <button
                        key={file}
                        className={`btn ${selectedFile === file ? "btn-primary" : ""}`}
                        style={{
                            textAlign: "left",
                            padding: "0.5rem",
                            background: selectedFile === file ? "var(--primary)" : "var(--bg)",
                            color: selectedFile === file ? "#fff" : "inherit",
                            border: "1px solid var(--border)",
                            borderRadius: "4px",
                            cursor: "pointer",
                        }}
                        onClick={() => setSelectedFile(file)}
                    >
                        {file}
                    </button>
                ))}
            </div>

            <div className="file-content" style={{ flex: 1, overflow: "hidden" }}>
                <CodeViewer
                    code={originalCode[selectedFile]}
                    language={guessLanguage(selectedFile)}
                    title={`File: ${selectedFile}`}
                />
            </div>
        </div>
    );
}

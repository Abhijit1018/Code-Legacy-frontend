/**
 * API client — communicates with the FastAPI backend.
 *
 * All calls go through the Vite dev-server proxy so we never
 * expose backend URLs or API keys to the browser.
 */

const BASE = import.meta.env.VITE_API_URL || "/api";

/**
 * POST /api/analyze-repo
 */
export async function analyzeRepo(repoUrl, branch = "main", targetLanguage = "python", options = {}) {
  const res = await fetch(`${BASE}/analyze-repo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      repo_url: repoUrl,
      branch,
      target_language: targetLanguage,
      compression_rate: options.compressionRate ?? 0.5,
      llm_model: options.llmModel ?? "nvidia/nemotron-3-super-120b-a12b:free",
      temperature: options.temperature ?? 0.2,
      max_tokens: options.maxTokens ?? 4096,
      remove_comments: options.removeComments ?? true,
      remove_tests: options.removeTests ?? true,
      github_token: options.githubToken ?? "",
      additional_instructions: options.additionalInstructions ?? "",
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

/**
 * POST /api/convert-repo
 */
export async function convertRepo(
  repoUrl,
  { branch = "main", targetLanguage = "python", compressionRate = 0.5, ...rest } = {}
) {
  const res = await fetch(`${BASE}/convert-repo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      repo_url: repoUrl,
      branch,
      target_language: targetLanguage,
      compression_rate: compressionRate,
      llm_model: rest.llmModel ?? "nvidia/nemotron-3-super-120b-a12b:free",
      temperature: rest.temperature ?? 0.2,
      max_tokens: rest.maxTokens ?? 4096,
      remove_comments: rest.removeComments ?? true,
      remove_tests: rest.removeTests ?? true,
      github_token: rest.githubToken ?? "",
      additional_instructions: rest.additionalInstructions ?? "",
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

/**
 * POST /api/analyze-snippet
 */
export async function analyzeSnippet(code, language = "cobol", targetLanguage = "python", options = {}) {
  const res = await fetch(`${BASE}/analyze-snippet`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      code,
      language,
      target_language: targetLanguage,
      llm_model: options.llmModel ?? "nvidia/nemotron-3-super-120b-a12b:free",
      temperature: options.temperature ?? 0.2,
      max_tokens: options.maxTokens ?? 4096,
      compression_rate: options.compressionRate ?? 0.5,
      additional_instructions: options.additionalInstructions ?? "",
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

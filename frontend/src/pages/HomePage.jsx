import React, { useState } from "react";
import RepoInput from "../components/RepoInput";
import ResultsView from "../components/ResultsView";
import LoadingSpinner from "../components/LoadingSpinner";
import { analyzeRepo } from "../api/client";

/**
 * HomePage — primary page of the application.
 *
 * User enters a GitHub repo URL → results are displayed below.
 */
export default function HomePage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const handleSubmit = async (
    repoUrl,
    branch,
    targetLanguage,
    options = {},
  ) => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await analyzeRepo(repoUrl, branch, targetLanguage, options);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <RepoInput onSubmit={handleSubmit} loading={loading} />

      {error && <div className="error-box">{error}</div>}

      {loading && <LoadingSpinner />}

      {result && <ResultsView data={result} />}
    </>
  );
}

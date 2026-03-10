import React from "react";

/**
 * LoadingSpinner — shown while the backend processes a request.
 */
export default function LoadingSpinner({ message = "Analysing repository…" }) {
  return (
    <div className="spinner-wrapper">
      <div className="spinner" />
      <p>{message}</p>
    </div>
  );
}

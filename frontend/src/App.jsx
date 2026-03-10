import React from "react";
import HomePage from "./pages/HomePage";

export default function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>Legacy Modernizer</h1>
        <p>
          AI-powered legacy code analysis &amp; modernisation — powered by
          Scaledown
        </p>
      </header>

      <main>
        <HomePage />
      </main>
    </div>
  );
}

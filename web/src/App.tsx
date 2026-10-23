import { lazy, Suspense } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { PlayPage } from "./pages/PlayPage";
import { RunDetailPage } from "./pages/RunDetailPage";
import { RunsPage } from "./pages/RunsPage";

const AnalysisPage = lazy(() =>
  import("./pages/AnalysisPage").then((m) => ({ default: m.AnalysisPage })),
);

export function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink className="brand" to="/play">
          MONO<span>POLY</span>
        </NavLink>
        <nav className="topnav">
          <NavLink to="/play">Play</NavLink>
          <NavLink to="/runs">Runs</NavLink>
          <NavLink to="/analysis">Analysis</NavLink>
        </nav>
        <div className="spacer" />
        <div className="round">
          hot-seat {"\u00b7"} {"2\u20136 players"}
        </div>
      </header>
      <main className="page">
        <Routes>
          <Route path="/" element={<Navigate to="/play" replace />} />
          <Route path="/play" element={<PlayPage />} />
          <Route path="/runs" element={<RunsPage />} />
          <Route path="/runs/:runId" element={<RunDetailPage />} />
          <Route
            path="/analysis"
            element={
              <Suspense fallback={<div className="loading">Loading analysis…</div>}>
                <AnalysisPage />
              </Suspense>
            }
          />
          <Route path="*" element={<Navigate to="/play" replace />} />
        </Routes>
      </main>
    </div>
  );
}

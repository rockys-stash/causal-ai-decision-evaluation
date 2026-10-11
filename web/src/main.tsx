import "@fontsource/geist-sans/400.css";
import "@fontsource/geist-sans/500.css";
import "@fontsource/geist-sans/600.css";
import "@fontsource/geist-mono/400.css";
import "@fontsource/geist-mono/500.css";
import "./styles.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout, StudyLayout } from "./components/Layout";
import { Design } from "./pages/Design";
import { Done } from "./pages/Done";
import { Method } from "./pages/Method";
import { NotFound } from "./pages/NotFound";
import { Overview } from "./pages/Overview";
import { Reliance } from "./pages/Reliance";
import { Results } from "./pages/Results";
import { SessionReplay, Sessions } from "./pages/Sessions";
import { Task } from "./pages/Task";
import { Welcome } from "./pages/Welcome";

const root = document.getElementById("root");
if (!root) throw new Error("missing #root element");

createRoot(root).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route index element={<Navigate to="/lab/overview" replace />} />
        <Route path="study" element={<StudyLayout />}>
          <Route index element={<Welcome />} />
          <Route path="task" element={<Task />} />
          <Route path="done" element={<Done />} />
        </Route>
        <Route path="lab" element={<Layout />}>
          <Route index element={<Navigate to="/lab/overview" replace />} />
          <Route path="overview" element={<Overview />} />
          <Route path="results" element={<Results />} />
          <Route path="reliance" element={<Reliance />} />
          <Route path="sessions" element={<Sessions />} />
          <Route path="sessions/:batch/:sid" element={<SessionReplay />} />
          <Route path="design" element={<Design />} />
          <Route path="method" element={<Method />} />
        </Route>
        <Route element={<Layout />}>
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);

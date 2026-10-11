import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

const NAV = [
  { to: "/lab/overview", label: "Overview" },
  { to: "/lab/results", label: "Results" },
  { to: "/lab/reliance", label: "Reliance & calibration" },
  { to: "/lab/sessions", label: "Sessions" },
  { to: "/lab/design", label: "Design" },
  { to: "/lab/method", label: "Method" },
];

type Theme = "system" | "light" | "dark";

function readTheme(): Theme {
  try {
    const t = localStorage.getItem("decision-lab-theme");
    return t === "light" || t === "dark" ? t : "system";
  } catch {
    return "system";
  }
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(readTheme);
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("decision-lab-theme", theme);
    } catch {
      /* storage unavailable: the preference lasts for this page view */
    }
  }, [theme]);
  const next: Record<Theme, Theme> = { system: "light", light: "dark", dark: "system" };
  return (
    <button className="btn ghost" type="button" onClick={() => setTheme(next[theme])} aria-label={`Theme: ${theme}. Switch to ${next[theme]}`}>
      Theme: {theme}
    </button>
  );
}

export function Logo() {
  return (
    <svg width="18" height="18" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <path d="M6 1.5v4.2L2.2 12.6A1.3 1.3 0 0 0 3.4 14.5h9.2a1.3 1.3 0 0 0 1.2-1.9L10 5.7V1.5" strokeLinejoin="round" />
      <path d="M5 1.5h6M4.2 9.5h7.6" strokeLinecap="round" />
    </svg>
  );
}

export function Layout() {
  const location = useLocation();
  useEffect(() => {
    document.getElementById("main")?.focus({ preventScroll: true });
  }, [location.pathname]);
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="topbar">
        <div className="topbar-inner">
          <div className="topbar-row">
            <NavLink to="/lab/overview" className="brand" aria-label="Decision Lab, researcher console overview">
              <span className="brand-mark">
                <Logo />
              </span>
              <span>
                <span className="brand-name">Decision Lab</span>
                <br />
                <span className="brand-sub">Human–AI decision experiment · researcher console</span>
              </span>
            </NavLink>
            <span className="deployment">Human study: pending</span>
            <ThemeToggle />
          </div>
          <nav className="tabs" aria-label="Sections">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} className={({ isActive }) => (isActive ? "active" : "")}>
                {n.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main id="main" className="main" tabIndex={-1}>
        <Outlet />
      </main>
    </>
  );
}

/** The participant's frame: no console navigation, nothing about other arms. */
export function StudyLayout() {
  const location = useLocation();
  useEffect(() => {
    document.getElementById("main")?.focus({ preventScroll: true });
  }, [location.pathname]);
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="topbar">
        <div className="topbar-inner">
          <div className="topbar-row">
            <span className="brand">
              <span className="brand-mark">
                <Logo />
              </span>
              <span>
                <span className="brand-name">Decision study</span>
                <br />
                <span className="brand-sub">Business decisions from real past cases</span>
              </span>
            </span>
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main id="main" className="main study" tabIndex={-1}>
        <Outlet />
      </main>
    </>
  );
}

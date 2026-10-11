import { Link } from "react-router-dom";

export function NotFound() {
  return (
    <div className="state">
      <h1>Page not found</h1>
      <p className="secondary">
        <Link to="/lab/overview">Researcher console</Link> · <Link to="/study">Participant study</Link>
      </p>
    </div>
  );
}

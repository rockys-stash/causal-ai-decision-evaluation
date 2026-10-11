const KEY = "decision-lab-session";

/** The participant's session id: the only credential for their session, kept for this tab. */
export function getSession(): string {
  try {
    return sessionStorage.getItem(KEY) ?? "";
  } catch {
    return "";
  }
}

export function setSession(id: string): void {
  try {
    if (id) sessionStorage.setItem(KEY, id);
    else sessionStorage.removeItem(KEY);
  } catch {
    /* storage unavailable: the session lasts for this page view */
  }
}

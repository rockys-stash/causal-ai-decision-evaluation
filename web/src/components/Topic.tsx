import type { ReactNode } from "react";
import { type ApiState, result, useApi } from "../lib/api";
import { ErrorOrPending, Loading, PageHead } from "./ui";

export function useTopic<T>(name: string): ApiState<T> {
  return useApi<T>(result(name));
}

/** Loading, pending (no pipeline result) and error states shared by every page. */
export function Gate<T>({
  state,
  title,
  what,
  children,
}: {
  state: ApiState<T>;
  title: string;
  what: string;
  children: (data: T) => ReactNode;
}) {
  if (state.loading && !state.data) return <Loading label={`Loading ${what}`} />;
  if (state.error)
    return (
      <>
        <PageHead title={title} />
        <ErrorOrPending error={state.error} retry={state.retry} what={what} command="make analysis" />
      </>
    );
  if (!state.data) return null;
  return <>{children(state.data)}</>;
}

import { useCallback, useState } from "react";

/** State kept in the query string (`?station=…&period=…`), so a view can be shared. */
export function useSearchParam(name: string): [string | null, (value: string) => void] {
  const [value, setValue] = useState(() => new URLSearchParams(window.location.search).get(name));
  const update = useCallback(
    (next: string) => {
      const url = new URL(window.location.href);
      url.searchParams.set(name, next);
      window.history.replaceState(null, "", url);
      setValue(next);
    },
    [name],
  );
  return [value, update];
}

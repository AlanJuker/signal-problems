import { useCallback, useState } from "react";

/** State kept in the query string (`?station=…&period=…`), so a view can be shared. */
export function useSearchParam(name: string): [string | null, (value: string | null) => void] {
  const [value, setValue] = useState(() => new URLSearchParams(window.location.search).get(name));
  const update = useCallback(
    (next: string | null) => {
      const url = new URL(window.location.href);
      if (next === null) url.searchParams.delete(name);
      else url.searchParams.set(name, next);
      window.history.replaceState(null, "", url);
      setValue(next);
    },
    [name],
  );
  return [value, update];
}

/**
 * Shared URL-state helpers for list pages (customers, agreements, later invoices).
 *
 * List pages keep their filters, sort and page in the URL (?search=&status=&page=),
 * so bookmarks, shared links and the back button all show the same view.
 */
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";

export type ParamChanges = Record<string, string | undefined>;

/**
 * Returns the current query params and a function to change some of them.
 * Any change other than the page itself resets to page 1 (a new filter starts at the top).
 */
export function useListSearchParams() {
  const [searchParams, setSearchParams] = useSearchParams();

  const updateParams = (changes: ParamChanges) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      for (const [key, value] of Object.entries(changes)) {
        if (value) next.set(key, value);
        else next.delete(key);
      }
      if (!("page" in changes)) next.delete("page");
      return next;
    });
  };

  return [searchParams, updateParams] as const;
}

/**
 * A search box whose value follows the URL.
 *
 * Typing updates the box at once; `commit` (which writes the URL, and so triggers the
 * API call) runs `delayMs` after the last keystroke instead of once per letter.
 * When the URL changes without typing (back button, a link that clears filters), the
 * box shows the URL's value; otherwise the debounce would put the old text back.
 */
export function useDebouncedUrlSearch(
  urlValue: string,
  commit: (value: string | undefined) => void,
  delayMs = 300,
) {
  const [input, setInput] = useState(urlValue);
  const lastCommitted = useRef(urlValue);
  // Keep the latest commit function without restarting the timer on every render.
  const commitRef = useRef(commit);
  commitRef.current = commit;

  useEffect(() => {
    const trimmed = input.trim();
    if (trimmed === urlValue) return;
    const timer = setTimeout(() => {
      lastCommitted.current = trimmed;
      commitRef.current(trimmed || undefined);
    }, delayMs);
    return () => clearTimeout(timer);
  }, [input, urlValue, delayMs]);

  useEffect(() => {
    if (urlValue !== lastCommitted.current) {
      lastCommitted.current = urlValue;
      setInput(urlValue);
    }
  }, [urlValue]);

  return [input, setInput] as const;
}

/** `value` if it is one of `allowed`, else undefined (ignores hand-typed nonsense in URLs). */
export function oneOf<T extends string>(value: string | null, allowed: readonly T[]): T | undefined {
  return allowed.includes(value as T) ? (value as T) : undefined;
}

/** A positive integer from the URL, or the fallback. */
export function positiveInt(value: string | null, fallback = 1): number {
  const number = Number(value);
  return Number.isInteger(number) && number > 0 ? number : fallback;
}

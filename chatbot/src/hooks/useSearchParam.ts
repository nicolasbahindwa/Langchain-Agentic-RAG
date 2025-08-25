import { useState, useCallback } from 'react';

// Custom hook for URL search params
export function useSearchParam(key: string): [string | null, (value: string | null) => void] {
  const [value, setValue] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    const params = new URLSearchParams(window.location.search);
    return params.get(key) ?? null;
  });

  const update = useCallback((newValue: string | null) => {
    setValue(newValue);
    if (typeof window === 'undefined') return;
    
    const url = new URL(window.location.href);
    if (newValue == null) {
      url.searchParams.delete(key);
    } else {
      url.searchParams.set(key, newValue);
    }
    window.history.pushState({}, '', url.toString());
  }, [key]);

  return [value, update];
}
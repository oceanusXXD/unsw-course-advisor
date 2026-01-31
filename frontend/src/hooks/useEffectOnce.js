// src/hooks/useEffectOnce.js
import { useEffect, useRef } from 'react';

export function useEffectOnce(effect) {
  const hasRun = useRef(false);
  const effectRef = useRef(effect);

  useEffect(() => {
    if (!hasRun.current) {
      hasRun.current = true;
      return effectRef.current();
    }
  }, []);
}

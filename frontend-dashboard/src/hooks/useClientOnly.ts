import { useState } from 'react';
import { useIsomorphicLayoutEffect } from './useIsomorphicLayoutEffect';

export function useClientOnly() {
  const [isClient, setIsClient] = useState(false);

  useIsomorphicLayoutEffect(() => {
    setIsClient(true);
  }, []);

  return isClient;
}
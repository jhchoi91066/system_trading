import { useEffect, useLayoutEffect } from 'react';

// SSR과 클라이언트 환경에서 안전하게 작동하는 훅
export const useIsomorphicLayoutEffect = typeof window !== 'undefined' ? useLayoutEffect : useEffect;
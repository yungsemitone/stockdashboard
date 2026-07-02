"use client";

import { useEffect, useState } from "react";

// Fired after the dashboard's instrument setup is saved, so open views refetch
// immediately instead of waiting for their next poll.
const EVT = "universe:changed";

export const bumpUniverse = () => window.dispatchEvent(new Event(EVT));

/** Bumps on every universe save — put it in poll deps to refetch on change. */
export function useUniverseVersion(): number {
  const [v, setV] = useState(0);
  useEffect(() => {
    const bump = () => setV((x) => x + 1);
    window.addEventListener(EVT, bump);
    return () => window.removeEventListener(EVT, bump);
  }, []);
  return v;
}

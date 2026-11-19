/**
 * Central registry of TanStack Query cache keys.
 *
 * Keys are hierarchical arrays. Invalidating ["customers"] later refreshes every
 * customer list and detail query at once, so keys must be built consistently.
 */
export const queryKeys = {
  auth: {
    me: ["auth", "me"] as const,
  },
  health: ["health"] as const,
};

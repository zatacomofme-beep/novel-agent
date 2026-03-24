"use client";

import { useEffect, useState } from "react";

import { buildUserFriendlyError } from "@/lib/errors";
import {
  fetchStoryBibleSaveStructure,
  resolveStoryBibleSaveBranchId,
} from "@/lib/story-bible-save";
import type { ProjectStructure } from "@/types/api";

export function useStoryBibleSaveTarget(
  projectId: string,
  preferredBranchId: string | null,
) {
  const [structure, setStructure] = useState<ProjectStructure | null>(null);
  const [branchId, setBranchId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadStructure() {
      try {
        const nextStructure = await fetchStoryBibleSaveStructure(projectId);
        if (cancelled) {
          return;
        }
        setStructure(nextStructure);
        setBranchId((current) =>
          resolveStoryBibleSaveBranchId(
            nextStructure,
            current ?? preferredBranchId,
          ),
        );
        setError(null);
      } catch (requestError) {
        if (cancelled) {
          return;
        }
        setError(buildUserFriendlyError(requestError));
      }
    }

    void loadStructure();

    return () => {
      cancelled = true;
    };
  }, [projectId, preferredBranchId]);

  return {
    structure,
    branchId,
    setBranchId,
    error,
  };
}

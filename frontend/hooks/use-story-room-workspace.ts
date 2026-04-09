"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetchWithAuth } from "@/lib/api";
import { buildUserFriendlyError } from "@/lib/errors";
import type {
  Chapter,
  ProjectBootstrapState,
  ProjectStructure,
  StoryBible,
  StoryBiblePendingChange,
  StoryBiblePendingChangeList,
  StoryBibleVersion,
  StoryBibleVersionList,
  StoryEngineWorkspace,
  StoryImportTemplate,
  UserPreferenceProfile,
  StyleTemplate,
} from "@/types/api";

function sortChapters(chapters: Chapter[]): Chapter[] {
  return [...chapters].sort((left, right) => {
    const branchCompare = (left.branch_id ?? "").localeCompare(right.branch_id ?? "");
    if (branchCompare !== 0) {
      return branchCompare;
    }
    const volumeCompare = (left.volume_id ?? "").localeCompare(right.volume_id ?? "");
    if (volumeCompare !== 0) {
      return volumeCompare;
    }
    return left.chapter_number - right.chapter_number;
  });
}

type UseStoryRoomWorkspaceOptions = {
  projectId: string;
};

type UseStoryRoomWorkspaceReturn = {
  workspace: StoryEngineWorkspace | null;
  bootstrapState: ProjectBootstrapState | null;
  storyBible: StoryBible | null;
  storyBibleVersions: StoryBibleVersion[];
  storyBiblePendingChanges: StoryBiblePendingChange[];
  preferenceProfile: UserPreferenceProfile | null;
  styleTemplates: StyleTemplate[];
  projectStructure: ProjectStructure | null;
  chapters: Chapter[];
  importTemplates: StoryImportTemplate[];
  loading: boolean;
  loadingStoryBibleGovernance: boolean;
  loadingStyleControl: boolean;
  error: string | null;
  loadWorkspace: (showSpinner?: boolean, branchId?: string | null) => Promise<void>;
  loadProjectBootstrap: (options?: { showError?: boolean; branchId?: string | null }) => Promise<ProjectBootstrapState | null>;
  loadStoryBibleForBranch: (branchId: string | null, showError?: boolean) => Promise<StoryBible | null>;
  loadStoryBibleGovernanceState: (branchId: string | null, showSpinner?: boolean) => Promise<{ versionData: StoryBibleVersionList; pendingData: StoryBiblePendingChangeList } | null>;
  loadStyleControlState: (showSpinner?: boolean) => Promise<{ profileData: UserPreferenceProfile; templateData: StyleTemplate[] } | null>;
  refreshChapterChainState: () => Promise<{ structureData: ProjectStructure; chapterData: Chapter[] }>;
  setError: (error: string | null) => void;
};

export function useStoryRoomWorkspace({
  projectId,
}: UseStoryRoomWorkspaceOptions): UseStoryRoomWorkspaceReturn {
  const [workspace, setWorkspace] = useState<StoryEngineWorkspace | null>(null);
  const [bootstrapState, setBootstrapState] = useState<ProjectBootstrapState | null>(null);
  const [storyBible, setStoryBible] = useState<StoryBible | null>(null);
  const [storyBibleVersions, setStoryBibleVersions] = useState<StoryBibleVersion[]>([]);
  const [storyBiblePendingChanges, setStoryBiblePendingChanges] = useState<StoryBiblePendingChange[]>([]);
  const [preferenceProfile, setPreferenceProfile] = useState<UserPreferenceProfile | null>(null);
  const [styleTemplates, setStyleTemplates] = useState<StyleTemplate[]>([]);
  const [projectStructure, setProjectStructure] = useState<ProjectStructure | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [importTemplates, setImportTemplates] = useState<StoryImportTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingStoryBibleGovernance, setLoadingStoryBibleGovernance] = useState(false);
  const [loadingStyleControl, setLoadingStyleControl] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshChapterChainState = useCallback(async () => {
    const [structureData, chapterData] = await Promise.all([
      apiFetchWithAuth<ProjectStructure>(`/api/v1/projects/${projectId}/structure`),
      apiFetchWithAuth<Chapter[]>(`/api/v1/projects/${projectId}/chapters`),
    ]);
    setProjectStructure(structureData);
    setChapters(sortChapters(chapterData));
    return { structureData, chapterData };
  }, [projectId]);

  const loadStoryBibleGovernanceState = useCallback(async (
    branchId: string | null,
    showSpinner = true,
  ) => {
    if (showSpinner) {
      setLoadingStoryBibleGovernance(true);
    }

    try {
      const query = branchId ? `?branch_id=${encodeURIComponent(branchId)}` : "";
      const [versionData, pendingData] = await Promise.all([
        apiFetchWithAuth<StoryBibleVersionList>(
          `/api/v1/projects/${projectId}/bible/versions${query}`,
        ),
        apiFetchWithAuth<StoryBiblePendingChangeList>(
          `/api/v1/projects/${projectId}/bible/pending-changes${query}`,
        ),
      ]);
      setStoryBibleVersions(versionData.items);
      setStoryBiblePendingChanges(pendingData.items);
      return { versionData, pendingData };
    } catch (requestError) {
      setStoryBibleVersions([]);
      setStoryBiblePendingChanges([]);
      setError(buildUserFriendlyError(requestError));
      return null;
    } finally {
      if (showSpinner) {
        setLoadingStoryBibleGovernance(false);
      }
    }
  }, [projectId]);

  const loadStyleControlState = useCallback(async (showSpinner = true) => {
    if (showSpinner) {
      setLoadingStyleControl(true);
    }

    try {
      const [profileData, templateData] = await Promise.all([
        apiFetchWithAuth<UserPreferenceProfile>("/api/v1/profile/preferences"),
        apiFetchWithAuth<StyleTemplate[]>("/api/v1/profile/style-templates"),
      ]);
      setPreferenceProfile(profileData);
      setStyleTemplates(templateData);
      return { profileData, templateData };
    } catch (requestError) {
      setPreferenceProfile(null);
      setStyleTemplates([]);
      return null;
    } finally {
      if (showSpinner) {
        setLoadingStyleControl(false);
      }
    }
  }, []);

  const loadStoryBibleForBranch = useCallback(async (
    branchId: string | null,
    showError = false,
  ) => {
    if (!branchId) {
      setStoryBible(null);
      return null;
    }
    try {
      const data = await apiFetchWithAuth<StoryBible>(
        `/api/v1/projects/${projectId}/bible?branch_id=${encodeURIComponent(branchId)}`,
      );
      setStoryBible(data);
      return data;
    } catch (requestError) {
      setStoryBible(null);
      if (showError) {
        setError(buildUserFriendlyError(requestError));
      }
      return null;
    }
  }, [projectId]);

  const loadWorkspace = useCallback(async (
    showSpinner = true,
    branchId: string | null = null,
  ) => {
    if (showSpinner) {
      setLoading(true);
    }
    setError(null);
    try {
      const query = branchId ? `?branch_id=${encodeURIComponent(branchId)}` : "";
      const [workspaceData, templateData] = await Promise.all([
        apiFetchWithAuth<StoryEngineWorkspace>(
          `/api/v1/projects/${projectId}/story-engine/workspace${query}`,
        ),
        apiFetchWithAuth<StoryImportTemplate[]>(
          `/api/v1/projects/${projectId}/story-engine/import-templates`,
        ),
        refreshChapterChainState(),
      ]);
      setWorkspace(workspaceData);
      setImportTemplates(templateData);
    } catch (requestError) {
      setError(buildUserFriendlyError(requestError));
    } finally {
      if (showSpinner) {
        setLoading(false);
      }
    }
  }, [projectId, refreshChapterChainState]);

  const loadProjectBootstrap = useCallback(async (
    options: {
      showError?: boolean;
      branchId?: string | null;
    } = {},
  ) => {
    const { showError = false, branchId = null } = options;
    try {
      const query = branchId ? `?branch_id=${encodeURIComponent(branchId)}` : "";
      const data = await apiFetchWithAuth<ProjectBootstrapState>(
        `/api/v1/projects/${projectId}/bootstrap${query}`,
      );
      setBootstrapState(data);
      return data;
    } catch (requestError) {
      if (showError) {
        setError(buildUserFriendlyError(requestError));
      }
      return null;
    }
  }, [projectId]);

  return {
    workspace,
    bootstrapState,
    storyBible,
    storyBibleVersions,
    storyBiblePendingChanges,
    preferenceProfile,
    styleTemplates,
    projectStructure,
    chapters,
    importTemplates,
    loading,
    loadingStoryBibleGovernance,
    loadingStyleControl,
    error,
    loadWorkspace,
    loadProjectBootstrap,
    loadStoryBibleForBranch,
    loadStoryBibleGovernanceState,
    loadStyleControlState,
    refreshChapterChainState,
    setError,
  };
}
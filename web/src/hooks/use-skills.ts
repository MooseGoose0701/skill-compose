'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { skillsApi, versionsApi, changelogsApi } from '@/lib/api';
import type {
  CreateSkillRequest,
  UpdateSkillRequest,
  CreateVersionRequest,
} from '@/types/skill';

// Query keys
export const skillKeys = {
  all: ['skills'] as const,
  lists: () => [...skillKeys.all, 'list'] as const,
  list: (filters: Record<string, unknown>) =>
    [...skillKeys.lists(), filters] as const,
  details: () => [...skillKeys.all, 'detail'] as const,
  detail: (name: string) => [...skillKeys.details(), name] as const,
  versions: (name: string) =>
    [...skillKeys.detail(name), 'versions'] as const,
  version: (name: string, version: string) =>
    [...skillKeys.versions(name), version] as const,
  changelogs: (name: string) =>
    [...skillKeys.detail(name), 'changelogs'] as const,
  tags: () => [...skillKeys.all, 'tags'] as const,
  categories: () => [...skillKeys.all, 'categories'] as const,
  githubStatus: () => [...skillKeys.all, 'githubStatus'] as const,
};

// List skills
export function useSkills(params?: {
  status?: string;
  tags?: string[];
  category?: string;
  sort_by?: string;
  sort_order?: string;
  offset?: number;
  limit?: number;
}) {
  return useQuery({
    queryKey: skillKeys.list(params || {}),
    queryFn: () => skillsApi.list(params),
  });
}

// List all unique tags
export function useTags() {
  return useQuery({
    queryKey: skillKeys.tags(),
    queryFn: () => skillsApi.listTags(),
  });
}

// List all unique categories
export function useCategories() {
  return useQuery({
    queryKey: skillKeys.categories(),
    queryFn: () => skillsApi.listCategories(),
  });
}

// Toggle pin state
export function useTogglePin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (name: string) => skillsApi.togglePin(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: skillKeys.lists() });
    },
  });
}

// Get skill detail
export function useSkill(name: string) {
  return useQuery({
    queryKey: skillKeys.detail(name),
    queryFn: () => skillsApi.get(name),
    enabled: !!name,
  });
}

// Create skill
export function useCreateSkill() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateSkillRequest) => skillsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: skillKeys.lists() });
    },
  });
}

// Update skill
export function useUpdateSkill(name: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateSkillRequest) => skillsApi.update(name, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: skillKeys.detail(name) });
      queryClient.invalidateQueries({ queryKey: skillKeys.lists() });
    },
  });
}

// Delete skill
export function useDeleteSkill() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (name: string) => skillsApi.delete(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: skillKeys.lists() });
    },
  });
}

// List versions
export function useVersions(
  skillName: string,
  params?: { offset?: number; limit?: number }
) {
  return useQuery({
    queryKey: skillKeys.versions(skillName),
    queryFn: () => versionsApi.list(skillName, params),
    enabled: !!skillName,
  });
}

// Get version detail
export function useVersion(skillName: string, version: string) {
  return useQuery({
    queryKey: skillKeys.version(skillName, version),
    queryFn: () => versionsApi.get(skillName, version),
    enabled: !!skillName && !!version,
  });
}

// Create version
export function useCreateVersion(skillName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateVersionRequest) =>
      versionsApi.create(skillName, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: skillKeys.versions(skillName),
      });
      queryClient.invalidateQueries({ queryKey: skillKeys.detail(skillName) });
    },
  });
}

// Rollback version
export function useRollback(skillName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (toVersion: string) =>
      versionsApi.rollback(skillName, toVersion),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: skillKeys.versions(skillName),
      });
      queryClient.invalidateQueries({ queryKey: skillKeys.detail(skillName) });
      queryClient.invalidateQueries({
        queryKey: skillKeys.changelogs(skillName),
      });
    },
  });
}

// Delete version
export function useDeleteVersion(skillName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (version: string) => versionsApi.delete(skillName, version),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: skillKeys.versions(skillName),
      });
      queryClient.invalidateQueries({ queryKey: skillKeys.detail(skillName) });
      queryClient.invalidateQueries({
        queryKey: skillKeys.changelogs(skillName),
      });
    },
  });
}

// List unregistered skills (on disk but not in DB)
export function useUnregisteredSkills() {
  return useQuery({
    queryKey: [...skillKeys.all, 'unregistered'] as const,
    queryFn: () => skillsApi.listUnregistered(),
  });
}

// Check GitHub update status for skills with GitHub source
export function useGithubUpdateStatus(hasGithubSkills: boolean) {
  return useQuery({
    queryKey: skillKeys.githubStatus(),
    queryFn: () => skillsApi.checkGithubUpdates(),
    enabled: hasGithubSkills,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });
}

// Get changelogs
export function useChangelogs(
  skillName: string,
  params?: { offset?: number; limit?: number }
) {
  return useQuery({
    queryKey: skillKeys.changelogs(skillName),
    queryFn: () => changelogsApi.list(skillName, params),
    enabled: !!skillName,
  });
}

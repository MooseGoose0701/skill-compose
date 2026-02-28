'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { scheduledTasksApi } from '@/lib/api';
import type { ScheduledTaskCreateRequest, ScheduledTaskUpdateRequest } from '@/lib/api';

// Query keys
export const scheduledTaskKeys = {
  all: ['scheduled-tasks'] as const,
  lists: () => [...scheduledTaskKeys.all, 'list'] as const,
  list: (filters: Record<string, unknown>) =>
    [...scheduledTaskKeys.lists(), filters] as const,
  details: () => [...scheduledTaskKeys.all, 'detail'] as const,
  detail: (id: string) => [...scheduledTaskKeys.details(), id] as const,
  runs: (taskId: string) => [...scheduledTaskKeys.detail(taskId), 'runs'] as const,
};

// List scheduled tasks
export function useScheduledTasks(params?: { status?: string }) {
  return useQuery({
    queryKey: scheduledTaskKeys.list(params || {}),
    queryFn: () => scheduledTasksApi.list(params),
  });
}

// Get scheduled task by ID
export function useScheduledTask(id: string) {
  return useQuery({
    queryKey: scheduledTaskKeys.detail(id),
    queryFn: () => scheduledTasksApi.get(id),
    enabled: !!id,
  });
}

// Create scheduled task
export function useCreateScheduledTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ScheduledTaskCreateRequest) => scheduledTasksApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.lists() });
    },
  });
}

// Update scheduled task
export function useUpdateScheduledTask(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ScheduledTaskUpdateRequest) => scheduledTasksApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.lists() });
    },
  });
}

// Delete scheduled task
export function useDeleteScheduledTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => scheduledTasksApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.lists() });
    },
  });
}

// Pause task
export function usePauseTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => scheduledTasksApi.pause(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.lists() });
    },
  });
}

// Resume task
export function useResumeTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => scheduledTasksApi.resume(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.lists() });
    },
  });
}

// Run task now
export function useRunTaskNow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => scheduledTasksApi.runNow(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.lists() });
      queryClient.invalidateQueries({ queryKey: scheduledTaskKeys.runs(id) });
    },
  });
}

// List task runs
export function useTaskRuns(taskId: string) {
  return useQuery({
    queryKey: scheduledTaskKeys.runs(taskId),
    queryFn: () => scheduledTasksApi.listRuns(taskId),
    enabled: !!taskId,
  });
}

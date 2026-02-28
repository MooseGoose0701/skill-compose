'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { channelsApi } from '@/lib/api';
import type { ChannelBindingCreateRequest, ChannelBindingUpdateRequest } from '@/lib/api';

// Query keys
export const channelKeys = {
  all: ['channels'] as const,
  lists: () => [...channelKeys.all, 'list'] as const,
  list: (filters: Record<string, unknown>) =>
    [...channelKeys.lists(), filters] as const,
  details: () => [...channelKeys.all, 'detail'] as const,
  detail: (id: string) => [...channelKeys.details(), id] as const,
  messages: (bindingId: string, params: Record<string, unknown>) =>
    [...channelKeys.all, 'messages', bindingId, params] as const,
  adapterStatus: () => [...channelKeys.all, 'adapter-status'] as const,
};

// List channel bindings
export function useChannelBindings(params?: { channel_type?: string }) {
  return useQuery({
    queryKey: channelKeys.list(params || {}),
    queryFn: () => channelsApi.list(params),
  });
}

// Get channel binding by ID
export function useChannelBinding(id: string) {
  return useQuery({
    queryKey: channelKeys.detail(id),
    queryFn: () => channelsApi.get(id),
    enabled: !!id,
  });
}

// Create channel binding
export function useCreateChannelBinding() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ChannelBindingCreateRequest) => channelsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: channelKeys.lists() });
    },
  });
}

// Update channel binding
export function useUpdateChannelBinding(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ChannelBindingUpdateRequest) => channelsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: channelKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: channelKeys.lists() });
    },
  });
}

// Delete channel binding
export function useDeleteChannelBinding() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => channelsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: channelKeys.lists() });
    },
  });
}

// Toggle channel binding enabled/disabled
export function useToggleChannelBinding() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => channelsApi.toggle(id),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: channelKeys.detail(data.id) });
      queryClient.invalidateQueries({ queryKey: channelKeys.lists() });
    },
  });
}

// List channel messages (paginated)
export function useChannelMessages(bindingId: string, params?: { limit?: number; offset?: number }) {
  return useQuery({
    queryKey: channelKeys.messages(bindingId, params || {}),
    queryFn: () => channelsApi.listMessages(bindingId, params),
    enabled: !!bindingId,
  });
}

// Get adapter connection status
export function useAdapterStatus() {
  return useQuery({
    queryKey: channelKeys.adapterStatus(),
    queryFn: () => channelsApi.adapterStatus(),
    refetchInterval: 30000, // Refresh every 30 seconds
  });
}

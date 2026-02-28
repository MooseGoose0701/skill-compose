'use client';

import { useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  ToggleLeft,
  ToggleRight,
  Trash2,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Spinner } from '@/components/ui/spinner';
import { ErrorBanner } from '@/components/ui/error-banner';
import { EmptyState } from '@/components/ui/empty-state';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { toast } from 'sonner';
import {
  useChannelBinding,
  useToggleChannelBinding,
  useDeleteChannelBinding,
  useChannelMessages,
} from '@/hooks/use-channels';
import { useTranslation } from '@/i18n/client';
import { formatDateTime } from '@/lib/formatters';

const PAGE_SIZE = 20;

export default function ChannelDetailPage() {
  const router = useRouter();
  const params = useParams();
  const bindingId = params.id as string;

  const { t } = useTranslation('channels');
  const { t: tc } = useTranslation('common');

  const { data: binding, isLoading, error } = useChannelBinding(bindingId);
  const toggleBinding = useToggleChannelBinding();
  const deleteBinding = useDeleteChannelBinding();

  const [messageOffset, setMessageOffset] = useState(0);
  const { data: messagesData, isLoading: messagesLoading } = useChannelMessages(bindingId, {
    limit: PAGE_SIZE,
    offset: messageOffset,
  });

  const messages = messagesData?.messages || [];
  const totalMessages = messagesData?.total || 0;
  const totalPages = Math.ceil(totalMessages / PAGE_SIZE);
  const currentPage = Math.floor(messageOffset / PAGE_SIZE) + 1;

  const handleToggle = async () => {
    if (!binding) return;
    try {
      await toggleBinding.mutateAsync(binding.id);
      toast.success(t('messages.toggled'));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tc('errors.generic'));
    }
  };

  const handleDelete = async () => {
    if (!binding) return;
    try {
      await deleteBinding.mutateAsync(binding.id);
      toast.success(t('messages.deleted'));
      router.push('/channels');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tc('errors.generic'));
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="container px-4 py-8">
        <ErrorBanner title={tc('errors.generic')} message={(error as Error).message} />
      </div>
    );
  }

  if (!binding) {
    return (
      <div className="container px-4 py-8">
        <ErrorBanner title={tc('errors.generic')} message="Binding not found" />
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen">
      <main className="flex-1 container px-4 py-8 max-w-4xl">
        {/* Back Link */}
        <Link
          href="/channels"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('title')}
        </Link>

        {/* Binding Details Card */}
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-start justify-between">
              <div>
                <CardTitle className="text-2xl">{binding.name}</CardTitle>
                <p className="text-sm text-muted-foreground mt-1">
                  {t('detail.title')}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleToggle}
                  disabled={toggleBinding.isPending}
                >
                  {toggleBinding.isPending ? (
                    <Spinner size="sm" className="mr-2" />
                  ) : binding.enabled ? (
                    <ToggleRight className="mr-2 h-4 w-4 text-green-500" />
                  ) : (
                    <ToggleLeft className="mr-2 h-4 w-4 text-muted-foreground" />
                  )}
                  {binding.enabled ? t('actions.disable') : t('actions.enable')}
                </Button>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="destructive" size="sm">
                      <Trash2 className="mr-2 h-4 w-4" />
                      {tc('actions.delete')}
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>{tc('actions.delete')}</AlertDialogTitle>
                      <AlertDialogDescription>
                        {t('messages.confirmDelete')}
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>{tc('actions.cancel')}</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={(e) => {
                          e.preventDefault();
                          handleDelete();
                        }}
                        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                      >
                        {tc('actions.delete')}
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <span className="text-sm font-medium text-muted-foreground">{t('fields.channelType')}</span>
                <div className="mt-1">
                  <Badge variant={binding.channel_type === 'feishu' ? 'info' : binding.channel_type === 'telegram' ? 'purple' : 'default'}>
                    {t(`channelTypes.${binding.channel_type}`) || binding.channel_type}
                  </Badge>
                </div>
              </div>
              <div>
                <span className="text-sm font-medium text-muted-foreground">{t('fields.externalId')}</span>
                <p className="mt-1 font-mono text-sm">{binding.external_id}</p>
              </div>
              <div>
                <span className="text-sm font-medium text-muted-foreground">{t('fields.agent')}</span>
                <p className="mt-1 text-sm">{binding.agent_id}</p>
              </div>
              <div>
                <span className="text-sm font-medium text-muted-foreground">{t('fields.enabled')}</span>
                <div className="mt-1">
                  <Badge variant={binding.enabled ? 'success' : 'secondary'}>
                    {binding.enabled ? t('actions.enable') : t('actions.disable')}
                  </Badge>
                </div>
              </div>
              {binding.trigger_pattern && (
                <div className="sm:col-span-2">
                  <span className="text-sm font-medium text-muted-foreground">{t('fields.triggerPattern')}</span>
                  <p className="mt-1">
                    <code className="text-sm bg-muted px-2 py-1 rounded">{binding.trigger_pattern}</code>
                  </p>
                </div>
              )}
              <div>
                <span className="text-sm font-medium text-muted-foreground">{tc('fields.createdAt')}</span>
                <p className="mt-1 text-sm">{formatDateTime(binding.created_at)}</p>
              </div>
              <div>
                <span className="text-sm font-medium text-muted-foreground">{tc('fields.updatedAt')}</span>
                <p className="mt-1 text-sm">{formatDateTime(binding.updated_at)}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Message History */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">{t('messages.title')}</CardTitle>
              {totalMessages > 0 && (
                <span className="text-sm text-muted-foreground">
                  {totalMessages} {tc('status.total').toLowerCase()}
                </span>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {messagesLoading ? (
              <div className="flex items-center justify-center py-8">
                <Spinner size="md" />
              </div>
            ) : messages.length === 0 ? (
              <EmptyState
                icon={ArrowLeft}
                title={t('messages.noMessages')}
                className="py-8"
              />
            ) : (
              <>
                <div className="rounded-md border overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-[100px]">{t('messages.direction.inbound')}</TableHead>
                        <TableHead className="w-[140px]">Sender</TableHead>
                        <TableHead>Content</TableHead>
                        <TableHead className="w-[180px]">{tc('fields.createdAt')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {messages.map((msg) => (
                        <TableRow key={msg.id}>
                          <TableCell>
                            <Badge
                              variant={msg.direction === 'inbound' ? 'info' : 'outline-success'}
                              className="text-xs"
                            >
                              {msg.direction === 'inbound'
                                ? t('messages.direction.inbound')
                                : t('messages.direction.outbound')}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-sm">
                            {msg.sender_name || msg.sender_id || '-'}
                          </TableCell>
                          <TableCell className="text-sm max-w-md truncate">
                            {msg.content}
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {formatDateTime(msg.created_at)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-between mt-4">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={currentPage <= 1}
                      onClick={() => setMessageOffset(Math.max(0, messageOffset - PAGE_SIZE))}
                    >
                      <ChevronLeft className="h-4 w-4 mr-1" />
                      {tc('actions.previous')}
                    </Button>
                    <span className="text-sm text-muted-foreground">
                      {currentPage} / {totalPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={currentPage >= totalPages}
                      onClick={() => setMessageOffset(messageOffset + PAGE_SIZE)}
                    >
                      {tc('actions.next')}
                      <ChevronRight className="h-4 w-4 ml-1" />
                    </Button>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}

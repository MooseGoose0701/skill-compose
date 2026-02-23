'use client';

import { useState } from 'react';
import { Globe, Copy, Check, ExternalLink, ChevronDown, Loader2, AlertTriangle } from 'lucide-react';
import { useTranslation } from '@/i18n/client';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface PublishCardProps {
  preset: {
    id: string;
    name: string;
    is_published: boolean;
    api_response_mode?: string | null;
  };
  isUnpublishing?: boolean;
  executorOffline?: boolean;
  executorName?: string;
  onPublish: () => void;
  onUnpublish: () => void;
}

export function PublishCard({ preset, isUnpublishing, executorOffline, executorName, onPublish, onUnpublish }: PublishCardProps) {
  const { t } = useTranslation('agents');
  const [copiedUrl, setCopiedUrl] = useState<string | null>(null);
  const [showApiUsage, setShowApiUsage] = useState(false);

  const copyToClipboard = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedUrl(key);
    setTimeout(() => setCopiedUrl(null), 2000);
  };

  const apiBase = typeof window !== 'undefined'
    ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:62610')
    : 'http://localhost:62610';
  const isStreaming = preset.api_response_mode === 'streaming';
  const endpoint = isStreaming ? 'chat' : 'chat/sync';

  if (preset.is_published) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Globe className="h-5 w-5 text-green-600" />
                <div>
                  <h3 className="font-semibold">{t('detail.publishedTitle')}</h3>
                  <p className="text-sm text-muted-foreground">{t('detail.publishedDescription')}</p>
                </div>
              </div>
              <Button variant="outline" onClick={onUnpublish} disabled={isUnpublishing}>
                {isUnpublishing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {t('unpublish.title')}
              </Button>
            </div>
            <div className="space-y-2 text-sm">
              {/* Mode Badge */}
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground shrink-0">{t('publish.responseMode.current')}:</span>
                <Badge variant={isStreaming ? 'info' : 'secondary'}>
                  {isStreaming ? t('publish.responseMode.streaming') : t('publish.responseMode.nonStreaming')}
                </Badge>
              </div>
              {/* Web Page URL */}
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground shrink-0">{t('detail.webPage')}:</span>
                <code className="bg-muted px-2 py-1 rounded text-xs flex-1 truncate">
                  {typeof window !== 'undefined' ? `${window.location.origin}/published/${preset.id}` : `/published/${preset.id}`}
                </code>
                <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => copyToClipboard(`${window.location.origin}/published/${preset.id}`, 'web')}>
                  {copiedUrl === 'web' ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
                </Button>
                <a href={`/published/${preset.id}`} target="_blank" rel="noopener noreferrer">
                  <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
                    <ExternalLink className="h-3.5 w-3.5" />
                  </Button>
                </a>
              </div>
              {/* API URL */}
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground shrink-0">{t('detail.apiLabel')}:</span>
                <code className="bg-muted px-2 py-1 rounded text-xs flex-1 truncate">
                  {`${apiBase}/api/v1/published/${preset.id}/${endpoint}`}
                </code>
                <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => copyToClipboard(`${apiBase}/api/v1/published/${preset.id}/${endpoint}`, 'api')}>
                  {copiedUrl === 'api' ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
                </Button>
              </div>
              {/* API Usage */}
              <div className="pt-1">
                <button
                  onClick={() => setShowApiUsage(!showApiUsage)}
                  className="flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors"
                >
                  <ChevronDown className={`h-4 w-4 transition-transform ${showApiUsage ? 'rotate-180' : ''}`} />
                  <span className="text-xs font-medium">{t('publish.apiUsage.title')}</span>
                </button>
                {showApiUsage && (
                  <div className="mt-2 space-y-3">
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-medium text-muted-foreground">{t('publish.apiUsage.exampleRequest')}</span>
                        <Button variant="ghost" size="sm" className="h-6 px-2 text-xs" onClick={() => {
                          const curl = isStreaming
                            ? `curl -N -X POST ${apiBase}/api/v1/published/${preset.id}/${endpoint} \\\n  -H "Content-Type: application/json" \\\n  -d '{"request": "Hello", "session_id": "your-session-id"}'`
                            : `curl -X POST ${apiBase}/api/v1/published/${preset.id}/${endpoint} \\\n  -H "Content-Type: application/json" \\\n  -d '{"request": "Hello", "session_id": "your-session-id"}'`;
                          copyToClipboard(curl, 'curl');
                        }}>
                          {copiedUrl === 'curl' ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3" />}
                        </Button>
                      </div>
                      <pre className="bg-muted rounded p-3 text-xs overflow-x-auto whitespace-pre">
{isStreaming
  ? `curl -N -X POST ${apiBase}/api/v1/published/${preset.id}/chat \\
  -H "Content-Type: application/json" \\
  -d '{"request": "Hello", "session_id": "your-session-id"}'`
  : `curl -X POST ${apiBase}/api/v1/published/${preset.id}/chat/sync \\
  -H "Content-Type: application/json" \\
  -d '{"request": "Hello", "session_id": "your-session-id"}'`}
                      </pre>
                      <p className="text-xs text-muted-foreground mt-1">
                        {isStreaming ? t('publish.apiUsage.streamingNote') : t('publish.apiUsage.nonStreamingNote')}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">{t('publish.apiUsage.sessionIdNote')}</p>
                    </div>
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-medium text-muted-foreground">{t('publish.apiUsage.sessionHistory')}</span>
                        <Button variant="ghost" size="sm" className="h-6 px-2 text-xs" onClick={() => copyToClipboard(`curl ${apiBase}/api/v1/published/${preset.id}/sessions/your-session-id`, 'session')}>
                          {copiedUrl === 'session' ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3" />}
                        </Button>
                      </div>
                      <pre className="bg-muted rounded p-3 text-xs overflow-x-auto whitespace-pre">
{`curl ${apiBase}/api/v1/published/${preset.id}/sessions/your-session-id`}
                      </pre>
                    </div>
                    <div className="flex items-center gap-1 pt-1">
                      <ExternalLink className="h-3 w-3 text-muted-foreground" />
                      <a
                        href={`${process.env.NEXT_PUBLIC_DOCS_URL || 'http://localhost:62630'}/how-to/publish-agent`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-primary hover:underline"
                      >
                        {t('publish.apiUsage.docsLink')}
                      </a>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold">{t('publish.title')}</h3>
            <p className="text-sm text-muted-foreground">{t('detail.publishDescription')}</p>
          </div>
          {executorOffline ? (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span tabIndex={0}>
                    <Button disabled>
                      <Globe className="mr-2 h-4 w-4" />
                      {t('publish.title')}
                    </Button>
                  </span>
                </TooltipTrigger>
                <TooltipContent side="top" className="max-w-xs">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
                    <p className="text-xs">{t('publish.executorOfflineWarning', { name: executorName })}</p>
                  </div>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          ) : (
            <Button onClick={onPublish}>
              <Globe className="mr-2 h-4 w-4" />
              {t('publish.title')}
            </Button>
          )}
        </div>
        {executorOffline && (
          <p className="text-xs text-destructive mt-2 flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" />
            {t('publish.executorOfflineWarning', { name: executorName })}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter, useParams } from 'next/navigation';
import {
  CheckCircle,
  XCircle,
  Clock,
  Cpu,
  Trash2,
  ChevronDown,
  ChevronRight,
  Loader2,
  Download,
  History,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { ErrorBanner } from '@/components/ui/error-banner';
import { LoadingSkeleton } from '@/components/ui/loading-skeleton';
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
import { useTrace, useDeleteTrace } from '@/hooks/use-traces';
import { useTranslation } from '@/i18n/client';
import { formatDuration, formatDateTime } from '@/lib/formatters';
import { tracesApi } from '@/lib/api';

interface StepInfo {
  role: string;
  content: string;
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  tool_result?: string;
}

function StepCard({ step, index, t }: { step: StepInfo; index: number; t: (key: string) => string }) {
  const [expanded, setExpanded] = useState(false);

  // For tool steps, show a meaningful summary in the collapsed view
  const getSummary = () => {
    if (step.tool_name && step.tool_input) {
      const input = step.tool_input;
      if (step.tool_name === 'execute_code' && input.code) {
        const code = String(input.code);
        const firstLine = code.split('\n')[0];
        return firstLine.length > 80 ? firstLine.slice(0, 80) + '...' : firstLine;
      }
      if (step.tool_name === 'execute_command' && input.command) {
        const cmd = String(input.command);
        return cmd.length > 80 ? cmd.slice(0, 80) + '...' : cmd;
      }
    }
    const content = step.content || '';
    return content.slice(0, 100) + (content.length > 100 ? '...' : '');
  };

  return (
    <Card className="p-3">
      <button
        type="button"
        className="flex items-center gap-2 cursor-pointer w-full text-left"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
        <span className="font-mono text-muted-foreground text-sm">{index + 1}.</span>
        {step.tool_name ? (
          <Badge variant="outline">{step.tool_name}</Badge>
        ) : (
          <Badge variant="secondary">{step.role}</Badge>
        )}
        <span className="truncate flex-1 text-sm font-mono">
          {getSummary()}
        </span>
      </button>
      {expanded && (
        <div className="mt-3 space-y-2 pl-6">
          {step.tool_input && Object.keys(step.tool_input).length > 0 && (
            <div>
              <span className="text-sm text-muted-foreground">{t('steps.input')}:</span>
              <pre className="text-xs bg-muted p-2 rounded mt-1 overflow-auto max-h-80 whitespace-pre-wrap">
                {JSON.stringify(step.tool_input, null, 2)}
              </pre>
            </div>
          )}
          <div>
            <span className="text-sm text-muted-foreground">{t('steps.output')}:</span>
            <pre className="text-xs bg-muted p-2 rounded mt-1 overflow-auto max-h-80 whitespace-pre-wrap">
              {step.content}
            </pre>
          </div>
          {step.tool_result && step.tool_result !== step.content && (
            <div>
              <span className="text-sm text-muted-foreground">{t('steps.result')}:</span>
              <pre className="text-xs bg-muted p-2 rounded mt-1 overflow-auto max-h-80 whitespace-pre-wrap">
                {step.tool_result}
              </pre>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

export default function TraceDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const { t } = useTranslation('traces');
  const { t: tc } = useTranslation('common');
  const router = useRouter();
  const { data: trace, isLoading, error } = useTrace(id);
  const deleteMutation = useDeleteTrace();

  const handleDelete = async () => {
    await deleteMutation.mutateAsync(id);
    router.push('/traces');
  };

  return (
    <div className="flex flex-col min-h-screen">
      {/* Main Content */}
      <main className="flex-1 container px-4 py-8">

        {/* Breadcrumb */}
        <nav className="flex items-center gap-1.5 text-sm text-muted-foreground mb-6">
          <Link href="/traces" className="flex items-center gap-1 hover:text-foreground transition-colors">
            <History className="h-4 w-4" />
            {t('detail.backToTraces')}
          </Link>
          <ChevronRight className="h-3.5 w-3.5" />
          <span className="text-foreground font-mono">#{id.slice(0, 8)}</span>
        </nav>

        {/* Error State */}
        {error && (
          <ErrorBanner title={t('detail.loadError')} message={(error as Error).message} className="mb-6" />
        )}

        {/* Loading State */}
        {isLoading && <LoadingSkeleton variant="detail" />}

        {/* Trace Detail */}
        {trace && (
          <div className="space-y-6">
            {/* Header */}
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  {trace.status === 'running' ? (
                    <Loader2 className="h-6 w-6 text-blue-500 animate-spin" />
                  ) : trace.status === 'cancelled' ? (
                    <XCircle className="h-6 w-6 text-yellow-500" />
                  ) : trace.success ? (
                    <CheckCircle className="h-6 w-6 text-green-500" />
                  ) : (
                    <XCircle className="h-6 w-6 text-red-500" />
                  )}
                  <h1 className="text-2xl font-bold">{t('detail.title')}</h1>
                  <Badge variant={
                    trace.status === 'running' ? 'secondary' :
                    trace.status === 'cancelled' ? 'warning' :
                    trace.success ? 'default' : 'destructive'
                  }>
                    {trace.status === 'running' ? t('status.running') :
                     trace.status === 'cancelled' ? t('status.cancelled') :
                     trace.success ? t('status.completed') : t('status.failed')}
                  </Badge>
                </div>
                <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Clock className="h-4 w-4" />
                    {formatDateTime(trace.created_at)}
                  </span>
                  <span className="flex items-center gap-1">
                    <Cpu className="h-4 w-4" />
                    {t('detail.turnsCount', { count: trace.total_turns })}
                  </span>
                  <span>
                    {t('detail.tokenStats', { input: trace.total_input_tokens, output: trace.total_output_tokens })}
                  </span>
                  <span>{formatDuration(trace.duration_ms)}</span>
                  <span className="font-mono text-xs">{trace.model}</span>
                </div>
              </div>
              <div className="flex gap-2">
                <a href={tracesApi.exportOne(id)} download>
                  <Button variant="outline" size="sm">
                    <Download className="h-4 w-4 mr-1" />
                    {tc('actions.export')}
                  </Button>
                </a>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="destructive" size="sm">
                      <Trash2 className="h-4 w-4 mr-1" />
                      {tc('actions.delete')}
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>{t('delete.title')}</AlertDialogTitle>
                      <AlertDialogDescription>
                        {t('delete.confirm')} {t('delete.description')}
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>{tc('actions.cancel')}</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={handleDelete}
                        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                      >
                        {tc('actions.delete')}
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </div>

            {/* Request */}
            <Card className="p-4">
              <h2 className="font-semibold mb-2">{t('detail.request')}</h2>
              <p className="whitespace-pre-wrap">{trace.request}</p>
            </Card>

            {/* Skills Used */}
            {trace.skills_used && trace.skills_used.length > 0 && (
              <Card className="p-4">
                <h2 className="font-semibold mb-2">{t('detail.skillsUsed')}</h2>
                <div className="flex flex-wrap gap-2">
                  {trace.skills_used.map((skill) => (
                    <Link key={skill} href={`/skills/${skill}`}>
                      <Badge variant="outline" className="cursor-pointer hover:bg-muted">
                        {skill}
                      </Badge>
                    </Link>
                  ))}
                </div>
              </Card>
            )}

            {/* Answer */}
            {trace.answer && (
              <Card className="p-4">
                <h2 className="font-semibold mb-2">{t('detail.answer')}</h2>
                <pre className="whitespace-pre-wrap text-sm">{trace.answer}</pre>
              </Card>
            )}

            {/* Error */}
            {trace.error && (
              <Card className="p-4 border-destructive/50">
                <h2 className="font-semibold mb-2 text-destructive">{t('detail.error')}</h2>
                <pre className="whitespace-pre-wrap text-sm text-destructive">{trace.error}</pre>
              </Card>
            )}

            {/* Execution Steps */}
            {trace.steps && trace.steps.length > 0 && (
              <div>
                <h2 className="font-semibold mb-3">{t('steps.titleWithCount', { count: trace.steps.length })}</h2>
                <div className="space-y-2">
                  {trace.steps.map((step, i) => (
                    <StepCard key={i} step={step as StepInfo} index={i} t={t} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

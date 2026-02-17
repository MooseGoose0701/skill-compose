'use client';

import { useState } from 'react';
import { Globe, Loader2, AlertCircle } from 'lucide-react';
import { useTranslation } from '@/i18n/client';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { ModelSelect } from '@/components/chat/selects';

interface ModelProvider {
  name: string;
  models: { key: string; display_name: string }[];
}

interface PublishDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  modelProviders: ModelProvider[];
  initialModelProvider: string | null;
  initialModelName: string | null;
  onPublish: (modelProvider: string | null, modelName: string | null, responseMode: 'streaming' | 'non_streaming') => void;
  isPublishing?: boolean;
}

export function PublishDialog({
  open,
  onOpenChange,
  modelProviders,
  initialModelProvider,
  initialModelName,
  onPublish,
  isPublishing = false,
}: PublishDialogProps) {
  const { t } = useTranslation('agents');
  const { t: tc } = useTranslation('common');

  const [modelProvider, setModelProvider] = useState<string | null>(initialModelProvider);
  const [modelName, setModelName] = useState<string | null>(initialModelName);
  const [responseMode, setResponseMode] = useState<'streaming' | 'non_streaming'>('streaming');

  // Reset state when dialog opens
  const handleOpenChange = (isOpen: boolean) => {
    if (isOpen) {
      setModelProvider(initialModelProvider);
      setModelName(initialModelName);
      setResponseMode('streaming');
    }
    onOpenChange(isOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('publish.title')}</DialogTitle>
          <DialogDescription>{t('publish.dialogDescription')}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Model Selection */}
          {modelProviders.length > 0 && (
            <div className="space-y-2">
              <Label>{t('create.modelLabel')}</Label>
              <ModelSelect
                value={null}
                modelProvider={modelProvider}
                modelName={modelName}
                onChange={(p, m) => { setModelProvider(p); setModelName(m); }}
                providers={modelProviders}
                placeholder={t('detail.modelDefault')}
                aria-label={t('create.modelLabel')}
              />
              <p className="text-xs text-muted-foreground">{t('publish.modelHelp')}</p>
            </div>
          )}

          {/* Warning if no model */}
          {!modelProvider && !modelName && (
            <div className="flex items-start gap-2 p-3 rounded-md bg-muted text-sm">
              <AlertCircle className="h-4 w-4 mt-0.5 shrink-0 text-muted-foreground" />
              <span className="text-muted-foreground">{t('publish.noModelWarning')}</span>
            </div>
          )}

          {/* API Response Mode */}
          <div className="space-y-3">
            <Label>{t('publish.responseMode.title')}</Label>
            <RadioGroup
              value={responseMode}
              onValueChange={(v) => setResponseMode(v as 'streaming' | 'non_streaming')}
              className="space-y-2"
            >
              <div className="flex items-start space-x-3 p-3 rounded-md border hover:bg-muted/50 cursor-pointer">
                <RadioGroupItem value="streaming" id="streaming" className="mt-1" />
                <div className="flex-1">
                  <Label htmlFor="streaming" className="font-medium cursor-pointer">{t('publish.responseMode.streaming')}</Label>
                  <p className="text-xs text-muted-foreground">{t('publish.responseMode.streamingDescription')}</p>
                </div>
              </div>
              <div className="flex items-start space-x-3 p-3 rounded-md border hover:bg-muted/50 cursor-pointer">
                <RadioGroupItem value="non_streaming" id="non_streaming" className="mt-1" />
                <div className="flex-1">
                  <Label htmlFor="non_streaming" className="font-medium cursor-pointer">{t('publish.responseMode.nonStreaming')}</Label>
                  <p className="text-xs text-muted-foreground">{t('publish.responseMode.nonStreamingDescription')}</p>
                </div>
              </div>
            </RadioGroup>
            <p className="text-xs text-muted-foreground">{t('publish.responseMode.immutableNote')}</p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isPublishing}>
            {tc('actions.cancel')}
          </Button>
          <Button onClick={() => onPublish(modelProvider, modelName, responseMode)} disabled={isPublishing}>
            {isPublishing ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {t('publish.publishing')}
              </>
            ) : (
              <>
                <Globe className="mr-2 h-4 w-4" />
                {t('publish.title')}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

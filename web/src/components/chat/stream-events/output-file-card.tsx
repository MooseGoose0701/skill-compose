"use client";

import { useState } from "react";
import { Download, FileText, Maximize2, Minimize2 } from "lucide-react";
import { formatFileSize } from "@/lib/formatters";
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import { VisuallyHidden } from "@radix-ui/react-visually-hidden";
import type { OutputFileData } from "@/types/stream-events";

interface OutputFileCardProps {
  data: OutputFileData;
}

const IMAGE_TYPES = new Set([
  "image/png", "image/jpeg", "image/gif", "image/svg+xml", "image/webp", "image/bmp", "image/tiff",
]);
const VIDEO_TYPES = new Set([
  "video/mp4", "video/webm", "video/ogg",
]);
const AUDIO_TYPES = new Set([
  "audio/mpeg", "audio/wav", "audio/ogg", "audio/mp3", "audio/flac", "audio/aac", "audio/webm",
]);

function isImage(ct: string) { return IMAGE_TYPES.has(ct); }
function isVideo(ct: string) { return VIDEO_TYPES.has(ct); }
function isAudio(ct: string) { return AUDIO_TYPES.has(ct); }
function isHtml(ct: string, filename: string) {
  return ct === "text/html" || filename.endsWith(".html") || filename.endsWith(".htm");
}

function FileInfo({ filename, size, downloadUrl }: { filename: string; size: number; downloadUrl: string }) {
  return (
    <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
      <span className="truncate">{filename}</span>
      <span>·</span>
      <span className="shrink-0">{formatFileSize(size)}</span>
      <a
        href={downloadUrl}
        download={filename}
        className="shrink-0 p-0.5 rounded hover:bg-muted transition-colors"
        onClick={(e) => e.stopPropagation()}
      >
        <Download className="h-3.5 w-3.5" />
      </a>
    </div>
  );
}

export function OutputFileCard({ data }: OutputFileCardProps) {
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:62610';
  const url = `${backendUrl}${data.downloadUrl}`;
  const ct = data.contentType || "";

  if (isImage(ct)) {
    return (
      <>
        <div className="my-1.5">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={url}
            alt={data.filename}
            onClick={() => setLightboxOpen(true)}
            className="max-w-md max-h-80 rounded-lg cursor-pointer hover:opacity-90 transition-opacity"
          />
          <FileInfo filename={data.filename} size={data.size} downloadUrl={url} />
        </div>
        <Dialog open={lightboxOpen} onOpenChange={setLightboxOpen}>
          <DialogContent className="max-w-[90vw] max-h-[90vh] w-auto p-2 flex items-center justify-center bg-black/95 border-none">
            <VisuallyHidden>
              <DialogTitle>{data.filename}</DialogTitle>
            </VisuallyHidden>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={url}
              alt={data.filename}
              className="max-w-[85vw] max-h-[85vh] object-contain"
            />
          </DialogContent>
        </Dialog>
      </>
    );
  }

  if (isVideo(ct)) {
    return (
      <div className="my-1.5">
        <video controls className="max-w-lg max-h-80 rounded-lg">
          <source src={url} type={ct} />
        </video>
        <FileInfo filename={data.filename} size={data.size} downloadUrl={url} />
      </div>
    );
  }

  if (isAudio(ct)) {
    return (
      <div className="my-1.5">
        <FileInfo filename={data.filename} size={data.size} downloadUrl={url} />
        <audio controls className="w-full max-w-md mt-1">
          <source src={url} type={ct} />
        </audio>
      </div>
    );
  }

  if (isHtml(ct, data.filename)) {
    return (
      <>
        <div className="my-1.5">
          <div className="relative border rounded-lg overflow-hidden bg-black">
            <iframe
              src={url}
              title={data.filename}
              sandbox="allow-scripts allow-same-origin"
              className="w-full border-0"
              style={{ height: 480, maxWidth: "100%" }}
            />
            <button
              onClick={() => setLightboxOpen(true)}
              className="absolute top-2 right-2 p-1.5 rounded-md bg-black/60 hover:bg-black/80 text-white transition-colors"
              title="Fullscreen"
            >
              <Maximize2 className="h-4 w-4" />
            </button>
          </div>
          <FileInfo filename={data.filename} size={data.size} downloadUrl={url} />
        </div>
        <Dialog open={lightboxOpen} onOpenChange={setLightboxOpen}>
          <DialogContent className="max-w-[95vw] max-h-[95vh] w-[95vw] h-[90vh] p-0 border-none bg-black">
            <VisuallyHidden>
              <DialogTitle>{data.filename}</DialogTitle>
            </VisuallyHidden>
            <div className="relative w-full h-full">
              <iframe
                src={url}
                title={data.filename}
                sandbox="allow-scripts allow-same-origin"
                className="w-full h-full border-0"
              />
              <button
                onClick={() => setLightboxOpen(false)}
                className="absolute top-3 right-3 p-1.5 rounded-md bg-black/60 hover:bg-black/80 text-white transition-colors"
                title="Exit fullscreen"
              >
                <Minimize2 className="h-4 w-4" />
              </button>
            </div>
          </DialogContent>
        </Dialog>
      </>
    );
  }

  // Default: download card for non-media files
  return (
    <a
      href={url}
      download={data.filename}
      className="flex items-center gap-3 p-3 my-1.5 border rounded-md bg-blue-50 dark:bg-blue-950/30 hover:bg-blue-100 dark:hover:bg-blue-950/50 transition-colors"
    >
      <div className="h-10 w-10 rounded-md bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center shrink-0">
        <FileText className="h-5 w-5 text-blue-600 dark:text-blue-400" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium truncate">{data.filename}</div>
        {data.description && (
          <div className="text-xs text-muted-foreground truncate">{data.description}</div>
        )}
        <div className="text-xs text-muted-foreground">{formatFileSize(data.size)}</div>
      </div>
      <Download className="h-5 w-5 text-blue-600 dark:text-blue-400 shrink-0" />
    </a>
  );
}

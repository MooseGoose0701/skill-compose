"use client";

import React, { useRef, useState, useEffect } from "react";
import { Markdown } from "./markdown";

interface LazyMarkdownProps {
  children: string;
  className?: string;
}

/**
 * Renders plain <pre> until the element scrolls into view (200px margin),
 * then upgrades to full <Markdown> (ReactMarkdown + Prism syntax highlighting).
 * This avoids paying the Markdown parsing cost for off-screen messages.
 */
export function LazyMarkdown({ children, className }: LazyMarkdownProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "200px" }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={ref}>
      {visible ? (
        <Markdown className={className}>{children}</Markdown>
      ) : (
        <pre className={`whitespace-pre-wrap font-sans text-sm ${className ?? ""}`}>{children}</pre>
      )}
    </div>
  );
}

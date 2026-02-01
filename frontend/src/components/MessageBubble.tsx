import { useMemo, useState } from "react";
import { marked } from "marked";
import type { Message, Source } from "@/hooks/useChat";

interface MessageBubbleProps {
  message: Message;
}

function SourcesSection({ sources }: { sources: Source[] }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="mt-2 border-t border-border pt-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        <span>{expanded ? "▼" : "▶"}</span>
        <span>
          {sources.length} relevant source{sources.length !== 1 ? "s" : ""}
        </span>
      </button>
      {expanded && (
        <div className="mt-2 space-y-2">
          {sources.map((source, i) => {
            const topic = source.metadata?.topic as string | undefined;
            const docType = source.metadata?.document_type as
              | string
              | undefined;
            return (
              <div
                key={`${source.document_id}-${source.chunk_index}-${i}`}
                className="rounded border border-border bg-background p-2 text-xs"
              >
                <div className="mb-1 flex flex-wrap items-center gap-1">
                  {docType && (
                    <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                      {docType}
                    </span>
                  )}
                  {topic && (
                    <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] font-medium text-secondary-foreground">
                      {topic}
                    </span>
                  )}
                  <span className="text-[10px] text-muted-foreground">
                    chunk {source.chunk_index}
                  </span>
                </div>
                <p className="text-muted-foreground leading-relaxed">
                  {source.content}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  const html = useMemo(() => {
    if (isUser || !message.content) return "";
    return marked.parse(message.content, { async: false }) as string;
  }, [isUser, message.content]);

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-2 text-sm ${
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-foreground"
        }`}
      >
        {isUser ? (
          <span className="whitespace-pre-wrap">{message.content}</span>
        ) : message.content === "" ? (
          <span className="inline-block animate-pulse">...</span>
        ) : (
          <div
            className="prose prose-sm dark:prose-invert max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0"
            dangerouslySetInnerHTML={{ __html: html }}
          />
        )}
        {!isUser && message.sources && message.sources.length > 0 && (
          <SourcesSection sources={message.sources} />
        )}
      </div>
    </div>
  );
}

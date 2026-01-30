import { useState, useCallback } from "react";
import { apiFetch } from "@/lib/api";

export interface Message {
  role: "user" | "assistant";
  content: string;
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  const sendMessage = useCallback(
    async (
      threadId: string,
      content: string,
      onTitleUpdate?: (title: string) => void
    ) => {
      setError(null);
      setMessages((prev) => [...prev, { role: "user", content }]);
      setMessages((prev) => [...prev, { role: "assistant", content: "" }]);
      setIsStreaming(true);

      try {
        const res = await apiFetch("/api/chat", {
          method: "POST",
          body: JSON.stringify({ thread_id: threadId, message: content }),
        });

        if (!res.ok) {
          const errorData = await res.json().catch(() => null);
          throw new Error(
            errorData?.detail || `Request failed with status ${res.status}`
          );
        }

        const reader = res.body?.getReader();
        if (!reader) throw new Error("No response body");

        const decoder = new TextDecoder();
        let buffer = "";
        let currentEvent = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("event: ")) {
              currentEvent = line.slice(7).trim();
              continue;
            }
            if (line.startsWith("data: ")) {
              const rawData = line.slice(6);
              try {
                const data = JSON.parse(rawData);
                if (currentEvent === "error" && data.error) {
                  throw new Error(data.error);
                } else if (data.text !== undefined) {
                  // delta event
                  setMessages((prev) => {
                    const updated = [...prev];
                    const last = updated[updated.length - 1];
                    if (last.role === "assistant") {
                      updated[updated.length - 1] = {
                        ...last,
                        content: last.content + data.text,
                      };
                    }
                    return updated;
                  });
                } else if (data.title !== undefined) {
                  // title_update event
                  onTitleUpdate?.(data.title);
                }
                // done event (response_id) — no client action needed
              } catch (e) {
                if (e instanceof Error && e.message !== "Unexpected end of JSON input") {
                  throw e;
                }
              }
            }
          }
        }
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to send message";
        setError(message);
        // Remove the empty assistant message on error
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant" && last.content === "") {
            return prev.slice(0, -1);
          }
          return prev;
        });
      } finally {
        setIsStreaming(false);
      }
    },
    []
  );

  const retryLastMessage = useCallback(
    async (threadId: string, onTitleUpdate?: (title: string) => void) => {
      const lastUserMsg = messages.filter((m) => m.role === "user").pop();
      if (!lastUserMsg) return;
      // Remove the failed user message so sendMessage can re-add it
      setMessages((prev) => {
        const idx = prev.lastIndexOf(lastUserMsg);
        if (idx >= 0) return [...prev.slice(0, idx), ...prev.slice(idx + 1)];
        return prev;
      });
      await sendMessage(threadId, lastUserMsg.content, onTitleUpdate);
    },
    [messages, sendMessage]
  );

  return { messages, isStreaming, error, sendMessage, clearMessages, retryLastMessage };
}

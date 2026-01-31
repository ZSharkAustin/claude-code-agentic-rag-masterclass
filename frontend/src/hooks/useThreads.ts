import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";

export interface Thread {
  id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export function useThreads() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchThreads = useCallback(async () => {
    try {
      const res = await apiFetch("/api/threads");
      if (res.ok) {
        const data = await res.json();
        setThreads(data);
      }
    } catch {
      // Silently fail — user may not be authenticated yet
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchThreads();
  }, [fetchThreads]);

  const createThread = async (): Promise<Thread | null> => {
    try {
      const res = await apiFetch("/api/threads", {
        method: "POST",
        body: JSON.stringify({ title: "New Chat" }),
      });
      if (res.ok) {
        const thread = await res.json();
        setThreads((prev) => [thread, ...prev]);
        return thread;
      }
    } catch {
      // Handle error
    }
    return null;
  };

  const updateThread = async (id: string, data: Partial<Thread>) => {
    try {
      const res = await apiFetch(`/api/threads/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      });
      if (res.ok) {
        const updated = await res.json();
        setThreads((prev) =>
          prev.map((t) => (t.id === id ? updated : t))
        );
      }
    } catch {
      // Handle error
    }
  };

  const deleteThread = async (id: string) => {
    try {
      const res = await apiFetch(`/api/threads/${id}`, {
        method: "DELETE",
      });
      if (res.ok || res.status === 204) {
        setThreads((prev) => prev.filter((t) => t.id !== id));
      }
    } catch {
      // Handle error
    }
  };

  return {
    threads,
    loading,
    createThread,
    updateThread,
    deleteThread,
    refreshThreads: fetchThreads,
  };
}

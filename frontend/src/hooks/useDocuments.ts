import { useState, useEffect, useCallback } from "react";
import { apiFetch, apiUpload } from "@/lib/api";
import { supabase } from "@/lib/supabase";

export interface Document {
  id: string;
  user_id: string;
  filename: string;
  file_path: string;
  file_size: number;
  mime_type: string;
  status: "uploading" | "processing" | "ready" | "error";
  chunk_count: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export function useDocuments() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchDocuments = useCallback(async () => {
    try {
      const res = await apiFetch("/api/documents");
      if (res.ok) {
        const data = await res.json();
        setDocuments(data);
      }
    } catch {
      // Silently fail
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  // Subscribe to Supabase Realtime for document status updates
  useEffect(() => {
    const channel = supabase
      .channel("documents-status")
      .on(
        "postgres_changes",
        { event: "UPDATE", schema: "public", table: "documents" },
        (payload) => {
          const updated = payload.new as Document;
          setDocuments((prev) =>
            prev.map((d) => (d.id === updated.id ? updated : d))
          );
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  const uploadDocument = useCallback(async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);

    const res = await apiUpload("/api/documents", formData);
    if (!res.ok) {
      const err = await res.json().catch(() => null);
      throw new Error(err?.detail || "Upload failed");
    }

    const doc: Document = await res.json();
    setDocuments((prev) => [doc, ...prev]);
    return doc;
  }, []);

  const deleteDocument = useCallback(async (id: string) => {
    const res = await apiFetch(`/api/documents/${id}`, { method: "DELETE" });
    if (res.ok || res.status === 204) {
      setDocuments((prev) => prev.filter((d) => d.id !== id));
    }
  }, []);

  return {
    documents,
    loading,
    uploadDocument,
    deleteDocument,
    refreshDocuments: fetchDocuments,
  };
}

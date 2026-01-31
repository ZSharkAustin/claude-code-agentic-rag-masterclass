import { useRef, useState } from "react";
import { Upload, Trash2, FileText, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useDocuments, type Document } from "@/hooks/useDocuments";

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function StatusBadge({ status }: { status: Document["status"] }) {
  const styles: Record<Document["status"], string> = {
    uploading: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
    processing: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
    ready: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
    error: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  };

  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${styles[status]}`}>
      {(status === "uploading" || status === "processing") && (
        <Loader2 className="h-3 w-3 animate-spin" />
      )}
      {status}
    </span>
  );
}

export function DocumentsPage() {
  const { documents, loading, uploadDocument, deleteDocument } = useDocuments();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setError(null);
    setUploading(true);
    try {
      await uploadDocument(file);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      // Reset file input so the same file can be re-selected
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div className="flex flex-1 flex-col p-6 max-w-4xl mx-auto w-full">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Documents</h2>
        <div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt,.md"
            className="hidden"
            onChange={handleUpload}
          />
          <Button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Upload className="mr-2 h-4 w-4" />
            )}
            Upload
          </Button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex flex-1 items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : documents.length === 0 ? (
        <div className="flex flex-1 items-center justify-center text-muted-foreground">
          <p>No documents uploaded yet. Upload a PDF, TXT, or MD file to get started.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center gap-4 rounded-lg border p-4"
            >
              <FileText className="h-8 w-8 shrink-0 text-muted-foreground" />
              <div className="flex-1 min-w-0">
                <p className="font-medium truncate">{doc.filename}</p>
                <div className="flex items-center gap-3 text-sm text-muted-foreground mt-1">
                  <span>{formatFileSize(doc.file_size)}</span>
                  {doc.chunk_count > 0 && (
                    <span>{doc.chunk_count} chunks</span>
                  )}
                  <StatusBadge status={doc.status} />
                </div>
                {doc.error_message && (
                  <p className="text-xs text-destructive mt-1">{doc.error_message}</p>
                )}
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => deleteDocument(doc.id)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

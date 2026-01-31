import { useState, useCallback } from "react";
import { Menu, MessageSquare, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { ThreadSidebar } from "@/components/ThreadSidebar";
import { MessageList } from "@/components/MessageList";
import { ChatInput } from "@/components/ChatInput";
import { UserMenu } from "@/components/UserMenu";
import { DocumentsPage } from "@/pages/DocumentsPage";
import { useThreads } from "@/hooks/useThreads";
import { useChat } from "@/hooks/useChat";

export function ChatPage() {
  const {
    threads,
    createThread,
    updateThread,
    deleteThread,
  } = useThreads();
  const { messages, isStreaming, error, sendMessage, clearMessages, loadMessages, retryLastMessage } =
    useChat();
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [view, setView] = useState<"chat" | "documents">("chat");

  const activeThread = threads.find((t) => t.id === activeThreadId);

  const handleSelectThread = useCallback(
    (id: string) => {
      setActiveThreadId(id);
      loadMessages(id);
      setMobileOpen(false);
    },
    [loadMessages]
  );

  const handleNewChat = useCallback(async () => {
    const thread = await createThread();
    if (thread) {
      setActiveThreadId(thread.id);
      clearMessages();
      setMobileOpen(false);
    }
  }, [createThread, clearMessages]);

  const handleDeleteThread = useCallback(
    async (id: string) => {
      await deleteThread(id);
      if (activeThreadId === id) {
        setActiveThreadId(null);
        clearMessages();
      }
    },
    [deleteThread, activeThreadId, clearMessages]
  );

  const handleSend = useCallback(
    (content: string) => {
      if (!activeThreadId) return;
      sendMessage(activeThreadId, content, (title) => {
        updateThread(activeThreadId, { title });
      });
    },
    [activeThreadId, sendMessage, updateThread]
  );

  const sidebar = (
    <ThreadSidebar
      threads={threads}
      activeThreadId={activeThreadId}
      onSelectThread={handleSelectThread}
      onNewChat={handleNewChat}
      onDeleteThread={handleDeleteThread}
    />
  );

  return (
    <div className="flex h-screen">
      {/* Desktop sidebar */}
      <div className="hidden md:block">{sidebar}</div>

      {/* Mobile sidebar */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetTrigger asChild className="md:hidden">
          <Button
            variant="ghost"
            size="icon"
            className="absolute left-4 top-3 z-10"
          >
            <Menu className="h-5 w-5" />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="w-[280px] p-0">
          {sidebar}
        </SheetContent>
      </Sheet>

      {/* Main area */}
      <div className="flex flex-1 flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b px-4 py-2">
          <div className="flex items-center gap-2 pl-10 md:pl-0">
            <div className="flex rounded-lg border p-0.5">
              <Button
                variant={view === "chat" ? "secondary" : "ghost"}
                size="sm"
                onClick={() => setView("chat")}
                className="gap-1.5"
              >
                <MessageSquare className="h-4 w-4" />
                Chat
              </Button>
              <Button
                variant={view === "documents" ? "secondary" : "ghost"}
                size="sm"
                onClick={() => setView("documents")}
                className="gap-1.5"
              >
                <FileText className="h-4 w-4" />
                Documents
              </Button>
            </div>
            {view === "chat" && (
              <h1 className="text-lg font-semibold truncate ml-2">
                {activeThread?.title || "Select a conversation"}
              </h1>
            )}
          </div>
          <UserMenu />
        </div>

        {/* Content */}
        {view === "documents" ? (
          <DocumentsPage />
        ) : activeThreadId ? (
          <>
            <MessageList messages={messages} />
            {error && (
              <div className="mx-auto max-w-3xl px-4 pb-2 flex items-center gap-2">
                <p className="text-sm text-destructive">{error}</p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    if (activeThreadId) {
                      retryLastMessage(activeThreadId, (title) => {
                        updateThread(activeThreadId, { title });
                      });
                    }
                  }}
                >
                  Retry
                </Button>
              </div>
            )}
            <ChatInput onSend={handleSend} disabled={isStreaming} />
          </>
        ) : (
          <div className="flex flex-1 items-center justify-center text-muted-foreground">
            <p>Create or select a conversation to get started.</p>
          </div>
        )}
      </div>
    </div>
  );
}

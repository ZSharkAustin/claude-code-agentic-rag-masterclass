import { MessageSquare, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Thread } from "@/hooks/useThreads";

interface ThreadItemProps {
  thread: Thread;
  isActive: boolean;
  onSelect: () => void;
  onDelete: () => void;
}

export function ThreadItem({
  thread,
  isActive,
  onSelect,
  onDelete,
}: ThreadItemProps) {
  return (
    <div
      className={`group flex items-center gap-2 rounded-md px-3 py-2 cursor-pointer hover:bg-accent ${
        isActive ? "bg-accent" : ""
      }`}
      onClick={onSelect}
    >
      <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
      <span className="truncate text-sm flex-1">{thread.title}</span>
      <Button
        variant="ghost"
        size="icon"
        className="h-6 w-6 opacity-0 group-hover:opacity-100"
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
      >
        <Trash2 className="h-3 w-3" />
      </Button>
    </div>
  );
}

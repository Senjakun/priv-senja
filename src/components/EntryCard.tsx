import { format } from "date-fns";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Entry {
  id: string;
  content: string;
  createdAt: Date;
}

interface EntryCardProps {
  entry: Entry;
  onDelete: (id: string) => void;
}

export const EntryCard = ({ entry, onDelete }: EntryCardProps) => {
  return (
    <article className="group gradient-card rounded-xl p-5 border border-border/30 hover:border-border/60 transition-all duration-300 hover:shadow-soft">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <time className="text-xs text-muted-foreground uppercase tracking-wider">
            {format(entry.createdAt, "EEEE, MMMM d, yyyy • h:mm a")}
          </time>
          <p className="mt-3 text-foreground/90 font-serif text-lg leading-relaxed whitespace-pre-wrap">
            {entry.content}
          </p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
          onClick={() => onDelete(entry.id)}
        >
          <Trash2 className="w-4 h-4" />
        </Button>
      </div>
    </article>
  );
};

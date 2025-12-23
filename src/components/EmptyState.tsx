import { BookOpen } from "lucide-react";

export const EmptyState = () => {
  return (
    <div className="flex flex-col items-center justify-center py-20 animate-fade-in">
      <div className="w-20 h-20 rounded-full bg-secondary/50 flex items-center justify-center mb-6 animate-float">
        <BookOpen className="w-10 h-10 text-primary" />
      </div>
      <h3 className="text-xl font-serif text-foreground mb-2">No entries yet</h3>
      <p className="text-muted-foreground text-center max-w-sm">
        Start capturing your thoughts as the day winds down. Your reflections are yours alone.
      </p>
    </div>
  );
};

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Send, X } from "lucide-react";

interface JournalEntryProps {
  onSave: (content: string) => void;
  onCancel: () => void;
}

export const JournalEntry = ({ onSave, onCancel }: JournalEntryProps) => {
  const [content, setContent] = useState("");

  const handleSubmit = () => {
    if (content.trim()) {
      onSave(content);
      setContent("");
    }
  };

  return (
    <div className="animate-fade-in-up">
      <div className="gradient-card rounded-2xl p-6 border border-border/50 shadow-soft">
        <Textarea
          placeholder="What's on your mind this evening..."
          value={content}
          onChange={(e) => setContent(e.target.value)}
          className="min-h-[200px] bg-transparent border-none resize-none text-foreground placeholder:text-muted-foreground focus-visible:ring-0 font-serif text-lg leading-relaxed"
          autoFocus
        />
        <div className="flex items-center justify-between mt-4 pt-4 border-t border-border/30">
          <span className="text-sm text-muted-foreground">
            {content.length} characters
          </span>
          <div className="flex gap-3">
            <Button variant="ghost" size="sm" onClick={onCancel}>
              <X className="w-4 h-4 mr-1" />
              Cancel
            </Button>
            <Button 
              variant="glow" 
              size="sm" 
              onClick={handleSubmit}
              disabled={!content.trim()}
            >
              <Send className="w-4 h-4 mr-1" />
              Save Entry
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

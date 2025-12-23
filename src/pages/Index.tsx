import { useState } from "react";
import { Plus, Moon, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { JournalEntry } from "@/components/JournalEntry";
import { EntryCard } from "@/components/EntryCard";
import { EmptyState } from "@/components/EmptyState";
import { useToast } from "@/hooks/use-toast";

interface Entry {
  id: string;
  content: string;
  createdAt: Date;
}

const Index = () => {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [isWriting, setIsWriting] = useState(false);
  const { toast } = useToast();

  const handleSaveEntry = (content: string) => {
    const newEntry: Entry = {
      id: crypto.randomUUID(),
      content,
      createdAt: new Date(),
    };
    setEntries([newEntry, ...entries]);
    setIsWriting(false);
    toast({
      title: "Entry saved",
      description: "Your thoughts have been captured.",
    });
  };

  const handleDeleteEntry = (id: string) => {
    setEntries(entries.filter((entry) => entry.id !== id));
    toast({
      title: "Entry deleted",
      description: "Your entry has been removed.",
    });
  };

  return (
    <div className="min-h-screen gradient-subtle">
      {/* Decorative background elements */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-twilight-start/5 rounded-full blur-3xl transform translate-x-1/2 -translate-y-1/2" />
        <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-twilight-end/10 rounded-full blur-3xl transform -translate-x-1/2 translate-y-1/2" />
      </div>

      <div className="relative z-10">
        {/* Header */}
        <header className="border-b border-border/30">
          <div className="container max-w-3xl mx-auto px-6 py-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl gradient-twilight flex items-center justify-center shadow-soft">
                  <Moon className="w-5 h-5 text-primary-foreground" />
                </div>
                <div>
                  <h1 className="text-xl font-serif font-semibold text-foreground">
                    Senja
                  </h1>
                  <p className="text-xs text-muted-foreground flex items-center gap-1">
                    <Lock className="w-3 h-3" />
                    Private journal
                  </p>
                </div>
              </div>
              {!isWriting && (
                <Button
                  variant="glow"
                  size="default"
                  onClick={() => setIsWriting(true)}
                  className="gap-2"
                >
                  <Plus className="w-4 h-4" />
                  New Entry
                </Button>
              )}
            </div>
          </div>
        </header>

        {/* Main content */}
        <main className="container max-w-3xl mx-auto px-6 py-10">
          {/* Writing area */}
          {isWriting && (
            <div className="mb-10">
              <JournalEntry
                onSave={handleSaveEntry}
                onCancel={() => setIsWriting(false)}
              />
            </div>
          )}

          {/* Entries list */}
          <section>
            {entries.length > 0 && (
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
                  Your Reflections
                </h2>
                <span className="text-sm text-muted-foreground">
                  {entries.length} {entries.length === 1 ? "entry" : "entries"}
                </span>
              </div>
            )}

            {entries.length === 0 && !isWriting ? (
              <EmptyState />
            ) : (
              <div className="space-y-4">
                {entries.map((entry, index) => (
                  <div
                    key={entry.id}
                    className="animate-fade-in-up"
                    style={{ animationDelay: `${index * 0.1}s` }}
                  >
                    <EntryCard entry={entry} onDelete={handleDeleteEntry} />
                  </div>
                ))}
              </div>
            )}
          </section>
        </main>

        {/* Footer */}
        <footer className="fixed bottom-0 left-0 right-0 border-t border-border/20 bg-background/80 backdrop-blur-sm">
          <div className="container max-w-3xl mx-auto px-6 py-4">
            <p className="text-center text-xs text-muted-foreground">
              Your thoughts are stored locally and remain completely private
            </p>
          </div>
        </footer>
      </div>
    </div>
  );
};

export default Index;

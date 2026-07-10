import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Trash2, Play } from "lucide-react";

export default function SessionsDialog({ open, onClose, sessions, onLoad, onDelete }) {
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="font-display tracking-tight">Saved Sessions</DialogTitle>
        </DialogHeader>
        <div className="mt-2 max-h-[420px] overflow-auto">
          {sessions.length === 0 ? (
            <div className="text-sm text-muted-foreground py-8 text-center">
              No saved sessions yet. Configure a plan and click Save.
            </div>
          ) : (
            <ul className="divide-y divide-border" data-testid="sessions-list">
              {sessions.map((s) => (
                <li key={s.id} className="py-3 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-semibold text-sm truncate">{s.name}</div>
                    <div className="overline mt-0.5">
                      {new Date(s.created_at).toLocaleString()} · {s.edits?.length || 0} edits · {s.prefs?.campaign_weeks || 0}w
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      onClick={() => onLoad(s.id)}
                      data-testid={`load-session-${s.id}`}
                    >
                      <Play className="h-4 w-4 mr-1" /> Load
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => onDelete(s.id)}
                      data-testid={`delete-session-${s.id}`}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

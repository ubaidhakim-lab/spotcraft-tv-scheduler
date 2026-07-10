import { Check } from "lucide-react";

export default function WizardHeader({ steps, current }) {
  return (
    <div className="bg-white border border-border" data-testid="wizard-header">
      <div className="flex">
        {steps.map((s, i) => {
          const done = current > s.id;
          const active = current === s.id;
          return (
            <div
              key={s.id}
              className={`flex-1 flex items-center gap-3 px-5 py-4 border-r border-border last:border-r-0 step-dot ${
                active ? "bg-primary text-white" : done ? "bg-primary/5" : "bg-white"
              }`}
              data-testid={`step-${s.key}`}
            >
              <div
                className={`h-7 w-7 flex items-center justify-center border ${
                  active
                    ? "bg-white text-primary border-white"
                    : done
                    ? "bg-primary text-white border-primary"
                    : "bg-white text-muted-foreground border-border"
                } font-display font-bold text-sm`}
              >
                {done ? <Check className="h-4 w-4" /> : s.id}
              </div>
              <div>
                <div className={`overline ${active ? "text-white/70" : ""}`}>Step {s.id}</div>
                <div className={`text-sm font-semibold ${active ? "text-white" : "text-foreground"}`}>
                  {s.label}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

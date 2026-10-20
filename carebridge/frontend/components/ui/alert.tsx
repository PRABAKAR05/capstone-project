import * as React from "react";
import { cn } from "@/lib/utils";
import { AlertCircle, CheckCircle2, Info, AlertTriangle } from "lucide-react";

export interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "info" | "success" | "warning" | "destructive";
}

export function Alert({ className, variant = "info", children, ...props }: AlertProps) {
  const variants = {
    info: "bg-blue-50/80 border-blue-200 text-blue-900",
    success: "bg-emerald-50/80 border-emerald-200 text-emerald-900",
    warning: "bg-amber-50/80 border-amber-200 text-amber-900",
    destructive: "bg-red-50/80 border-red-200 text-red-900",
  };

  const icons = {
    info: <Info className="h-4 w-4 text-blue-600 shrink-0" />,
    success: <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />,
    warning: <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />,
    destructive: <AlertCircle className="h-4 w-4 text-red-600 shrink-0" />,
  };

  return (
    <div
      role="alert"
      className={cn(
        "relative w-full rounded-lg border p-3 flex items-start gap-3 text-xs leading-relaxed",
        variants[variant],
        className
      )}
      {...props}
    >
      {icons[variant]}
      <div className="flex-1 space-y-0.5">{children}</div>
    </div>
  );
}

export function AlertTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h5 className={cn("font-bold tracking-tight text-xs", className)} {...props} />;
}

export function AlertDescription({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <div className={cn("text-xs opacity-90", className)} {...props} />;
}

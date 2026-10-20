import * as React from "react";
import { cn } from "@/lib/utils";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "ghost" | "destructive" | "accent";
  size?: "sm" | "md" | "lg" | "icon";
  isLoading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", isLoading = false, children, disabled, ...props }, ref) => {
    const baseStyles =
      "inline-flex items-center justify-center font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 disabled:pointer-events-none disabled:opacity-50 select-none cursor-pointer";

    const variants = {
      primary: "bg-blue-700 text-white hover:bg-blue-800 active:bg-blue-900 shadow-sm",
      secondary: "bg-slate-100 text-slate-800 hover:bg-slate-200 active:bg-slate-300 border border-slate-200",
      outline: "border border-slate-300 bg-transparent hover:bg-slate-50 text-slate-700 active:bg-slate-100",
      ghost: "hover:bg-slate-100 text-slate-700 active:bg-slate-200",
      destructive: "bg-red-600 text-white hover:bg-red-700 active:bg-red-800 shadow-sm",
      accent: "bg-teal-600 text-white hover:bg-teal-700 active:bg-teal-800 shadow-sm",
    };

    const sizes = {
      sm: "h-8 px-3 text-xs rounded-md",
      md: "h-9 px-4 text-sm rounded-md",
      lg: "h-11 px-6 text-base rounded-lg",
      icon: "h-9 w-9 p-0 rounded-md",
    };

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(baseStyles, variants[variant], sizes[size], className)}
        {...props}
      >
        {isLoading && (
          <svg
            className="animate-spin -ml-1 mr-2 h-4 w-4 text-current"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        )}
        {children}
      </button>
    );
  }
);
Button.displayName = "Button";

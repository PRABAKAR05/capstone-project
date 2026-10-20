"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  CalendarPlus,
  Stethoscope,
  Building2,
  FileText,
  ClipboardList,
  FlaskConical,
  ShieldCheck,
} from "lucide-react";

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  roles: string[];
}

const NAV_ITEMS: NavItem[] = [
  // Patient
  {
    label: "My Health Portal",
    href: "/portal",
    icon: LayoutDashboard,
    roles: ["patient", "hospital_admin"],
  },
  {
    label: "Book Appointment",
    href: "/portal/book",
    icon: CalendarPlus,
    roles: ["patient", "hospital_admin"],
  },
  {
    label: "Clinical Records",
    href: "/portal/documents",
    icon: FileText,
    roles: ["patient", "hospital_admin"],
  },

  // Doctor
  {
    label: "Doctor Workstation",
    href: "/doctor",
    icon: Stethoscope,
    roles: ["doctor", "hospital_admin"],
  },

  // Nurse
  {
    label: "Nurse Desk & Intake",
    href: "/nurse",
    icon: Stethoscope,
    roles: ["nurse", "hospital_admin"],
  },

  // Care Coordination Tasks (Doctor, Nurse, Admin)
  {
    label: "Care Coordination Tasks",
    href: "/tasks",
    icon: ClipboardList,
    roles: ["doctor", "nurse", "hospital_admin"],
  },

  // Lab Technician
  {
    label: "Laboratory Workstation",
    href: "/lab",
    icon: FlaskConical,
    roles: ["lab_technician", "hospital_admin"],
  },

  // Admin
  {
    label: "Hospital Operations",
    href: "/admin",
    icon: Building2,
    roles: ["hospital_admin"],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();

  const userRole = user?.role || "patient";
  const visibleNav = NAV_ITEMS.filter((item) => item.roles.includes(userRole));

  return (
    <aside className="w-64 border-r border-slate-200/80 bg-white min-h-[calc(100vh-3.5rem)] flex flex-col p-4 space-y-6">
      <div className="space-y-1">
        <p className="px-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">
          Navigation
        </p>
        <nav className="space-y-1">
          {visibleNav.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center space-x-3 rounded-lg px-3 py-2 text-xs font-semibold transition-colors",
                  isActive
                    ? "bg-blue-50 text-blue-700 font-bold"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                )}
              >
                <Icon
                  className={cn(
                    "h-4 w-4",
                    isActive ? "text-blue-700" : "text-slate-400"
                  )}
                />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Security Invariant Notice Card */}
      <div className="mt-auto rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-1.5 text-[11px] text-slate-600">
        <div className="flex items-center space-x-1.5 text-blue-700 font-bold text-xs">
          <ShieldCheck className="h-4 w-4 shrink-0" />
          <span>Security Invariant</span>
        </div>
        <p className="text-[10px] leading-relaxed text-slate-500">
          Zero-trust client model: API authorization is verified by FastAPI and PostgreSQL Row Level Security on every request.
        </p>
      </div>
    </aside>
  );
}

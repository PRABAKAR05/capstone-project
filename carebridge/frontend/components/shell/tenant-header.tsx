"use client";

import * as React from "react";
import { useAuth, SYNTHETIC_DEMO_ACCOUNTS, DemoAccount } from "@/lib/auth-context";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Building2, Clock, User, LogOut, UserCheck } from "lucide-react";

export function TenantHeader() {
  const { user, hospital, signOut, selectDemoAccount } = useAuth();
  const [currentTime, setCurrentTime] = React.useState<string>("");
  const [switcherOpen, setSwitcherOpen] = React.useState(false);

  React.useEffect(() => {
    function updateClock() {
      const now = new Date();
      const timeStr = now.toLocaleTimeString("en-IN", {
        timeZone: hospital?.timezone || "Asia/Kolkata",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: true,
      });
      setCurrentTime(timeStr);
    }
    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, [hospital?.timezone]);

  const roleBadgeVariants: Record<string, "default" | "teal" | "warning" | "success" | "secondary"> = {
    hospital_admin: "default",
    doctor: "teal",
    receptionist: "warning",
    patient: "success",
    caregiver: "secondary",
  };

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-200/90 bg-white/95 backdrop-blur-xs">
      <div className="flex h-14 items-center justify-between px-4 sm:px-6">
        {/* Hospital Branding & Tenant Identity */}
        <div className="flex items-center space-x-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-700 text-white font-black text-base shadow-xs">
            CB
          </div>
          <div className="flex flex-col">
            <div className="flex items-center space-x-2">
              <span className="text-sm font-bold tracking-tight text-slate-900">CareBridge AI</span>
              <span className="hidden sm:inline-block text-xs text-slate-400">|</span>
              <span className="hidden sm:inline-flex items-center text-xs font-semibold text-slate-700">
                <Building2 className="mr-1 h-3.5 w-3.5 text-blue-600" />
                {hospital?.name || "Aegis Metro General Hospital"}
              </span>
            </div>
            <span className="text-[11px] text-slate-500 hidden md:block">
              Autonomous Clinical Operations & Care Coordination
            </span>
          </div>
        </div>

        {/* Timezone Clock & User Persona Info */}
        <div className="flex items-center space-x-2 sm:space-x-4">
          {/* Hospital Timezone Clock */}
          <div className="hidden lg:flex items-center space-x-1.5 rounded-md bg-slate-50 px-2.5 py-1 border border-slate-200 text-xs font-mono text-slate-700">
            <Clock className="h-3.5 w-3.5 text-blue-600" />
            <span>{currentTime || "Loading..."}</span>
            <span className="text-[10px] text-slate-400 font-sans">({hospital?.timezone || "Asia/Kolkata"})</span>
          </div>

          {/* Active User Badge & Persona Switcher */}
          {user && (
            <div className="flex items-center space-x-2">
              <button
                onClick={() => setSwitcherOpen(true)}
                className="flex items-center space-x-2 rounded-lg border border-slate-200 bg-slate-50/80 px-2.5 py-1 text-xs hover:bg-slate-100 transition-colors text-left"
                title="Click to switch demonstration persona"
              >
                <div className="h-6 w-6 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-xs">
                  <User className="h-3.5 w-3.5" />
                </div>
                <div className="hidden sm:flex flex-col">
                  <span className="font-semibold text-slate-800 text-[11px] leading-tight truncate max-w-[120px]">
                    {user.full_name || user.email}
                  </span>
                  <span className="text-[10px] text-slate-500 capitalize">{user.role.replace("_", " ")}</span>
                </div>
                <Badge variant={roleBadgeVariants[user.role] || "default"} className="text-[10px] py-0 px-1.5">
                  {user.role === "hospital_admin" ? "Admin" : user.role}
                </Badge>
              </button>

              <Button
                variant="ghost"
                size="sm"
                onClick={async () => {
                  await signOut();
                }}
                className="text-slate-500 hover:text-red-600 h-8 px-2"
                title="Sign Out"
              >
                <LogOut className="h-4 w-4" />
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Persona Switcher Modal for Easy Demonstration Testing */}
      <Dialog open={switcherOpen} onOpenChange={setSwitcherOpen}>
        <DialogContent onClose={() => setSwitcherOpen(false)}>
          <DialogHeader>
            <DialogTitle>Demonstration Persona Switcher</DialogTitle>
            <DialogDescription>
              Select a verified synthetic persona to test role-based views. Backend verifies privileges on each API call.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2 py-2">
            {SYNTHETIC_DEMO_ACCOUNTS.map((acc: DemoAccount) => (
              <button
                key={acc.email}
                onClick={async () => {
                  await selectDemoAccount(acc, acc.password);
                  setSwitcherOpen(false);
                }}
                className={`w-full text-left p-3 rounded-lg border transition-all flex items-start space-x-3 cursor-pointer ${
                  user?.role === acc.role
                    ? "border-blue-600 bg-blue-50/50"
                    : "border-slate-200 hover:bg-slate-50"
                }`}
              >
                <div
                  className={`mt-0.5 p-1.5 rounded-md ${
                    user?.role === acc.role ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600"
                  }`}
                >
                  <UserCheck className="h-4 w-4" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-900">{acc.label}</span>
                    <Badge variant={roleBadgeVariants[acc.role] || "default"} className="text-[10px]">
                      {acc.role}
                    </Badge>
                  </div>
                  <p className="text-[11px] text-slate-500 mt-0.5">{acc.email}</p>
                  <p className="text-[11px] text-slate-600 mt-1">{acc.description}</p>
                </div>
              </button>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </header>
  );
}

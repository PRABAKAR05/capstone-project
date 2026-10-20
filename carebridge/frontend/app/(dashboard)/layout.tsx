import * as React from "react";
import { Suspense } from "react";
import { TenantHeader } from "@/components/shell/tenant-header";
import { Sidebar } from "@/components/shell/sidebar";
import { ConversationalDrawer } from "@/components/chat/conversational-drawer";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <Suspense fallback={<div className="h-16 bg-white border-b border-slate-200" />}>
        <TenantHeader />
      </Suspense>
      <div className="flex flex-1">
        <Suspense fallback={<div className="w-64 bg-white border-r border-slate-200" />}>
          <Sidebar />
        </Suspense>
        <main className="flex-1 p-6 md:p-8 max-w-7xl mx-auto w-full">
          <Suspense fallback={<div className="p-8 text-sm text-slate-400">Loading view...</div>}>
            {children}
          </Suspense>
        </main>
      </div>
      <ConversationalDrawer />
    </div>
  );
}


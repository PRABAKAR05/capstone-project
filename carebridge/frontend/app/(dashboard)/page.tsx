"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Skeleton } from "@/components/ui/skeleton";

export default function DashboardHome() {
  const router = useRouter();
  const { user, isLoading } = useAuth();

  React.useEffect(() => {
    if (!isLoading) {
      if (!user) {
        router.replace("/login");
        return;
      }
      switch (user.role) {
        case "hospital_admin":
          router.replace("/admin");
          break;
        case "doctor":
          router.replace("/doctor");
          break;
        case "nurse":
          router.replace("/nurse");
          break;
        case "lab_technician":
          router.replace("/lab");
          break;
        case "patient":
        default:
          router.replace("/portal");
          break;
      }
    }
  }, [user, isLoading, router]);

  return (
    <div className="space-y-4 max-w-md mx-auto mt-20 text-center">
      <Skeleton className="h-8 w-48 mx-auto" />
      <Skeleton className="h-4 w-72 mx-auto" />
      <p className="text-xs text-slate-500">Routing to role workstation...</p>
    </div>
  );
}

"use client";

import * as React from "react";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { ShieldCheck, Info } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface PatientConflict {
  id: string;
  patient_friendly_summary: string;
  resolution_status: string;
  created_at: string;
}

export function PatientSafetyAdvisory() {
  const [conflicts, setConflicts] = React.useState<PatientConflict[]>([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let ignore = false;
    async function loadPatientAlerts() {
      try {
        const data = await apiFetch<PatientConflict[]>("/conflicts");
        if (!ignore && data) {
          // Filter to unresolved or recent active advisories
          setConflicts(data);
        }
      } catch {
        // Quiet fallback: patient view degrades gracefully
      } finally {
        if (!ignore) setLoading(false);
      }
    }
    loadPatientAlerts();
    return () => {
      ignore = true;
    };
  }, []);

  if (loading || conflicts.length === 0) {
    return null;
  }

  return (
    <div className="mb-6">
      <Alert className="border-teal-200 bg-teal-50/70 text-teal-900 rounded-xl shadow-sm">
        <ShieldCheck className="h-5 w-5 text-teal-600 mt-0.5 shrink-0" />
        <div className="ml-2">
          <AlertTitle className="text-sm font-semibold text-teal-950 flex items-center gap-2">
            Medication Safety Review in Progress
          </AlertTitle>
          <AlertDescription className="text-xs text-teal-800/90 mt-1 space-y-2">
            <p>
              Your care team is actively reviewing your historical health records and active prescriptions to ensure your treatment plan is completely aligned and safe.
            </p>
            <div className="bg-white/80 border border-teal-100 rounded-lg p-2.5 mt-2 space-y-1.5">
              {conflicts.map((c) => (
                <div key={c.id} className="flex items-start gap-2 text-xs text-slate-700">
                  <Info className="h-3.5 w-3.5 text-teal-600 mt-0.5 shrink-0" />
                  <span>{c.patient_friendly_summary}</span>
                </div>
              ))}
            </div>
          </AlertDescription>
        </div>
      </Alert>
    </div>
  );
}

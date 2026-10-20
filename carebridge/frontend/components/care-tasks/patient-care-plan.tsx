"use client";

import * as React from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiFetch } from "@/lib/api";
import { ClipboardCheck, Clock } from "lucide-react";

interface PatientTask {
  id: string;
  task_type: string;
  priority: string;
  status: string;
  title: string;
  patient_instructions?: string;
  due_date?: string;
  created_at: string;
}

export function PatientCarePlan() {
  const [tasks, setTasks] = React.useState<PatientTask[]>([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let ignore = false;
    async function loadTasks() {
      try {
        const data = await apiFetch<PatientTask[]>("/care-tasks");
        if (!ignore && data) {
          // Filter to active care plan instructions
          setTasks(data.filter((t) => t.status !== "completed" && t.status !== "cancelled"));
        }
      } catch {
        // Fallback gracefully
      } finally {
        if (!ignore) setLoading(false);
      }
    }
    loadTasks();
    return () => {
      ignore = true;
    };
  }, []);

  if (loading || tasks.length === 0) {
    return null;
  }

  return (
    <Card className="border-blue-100 bg-gradient-to-r from-blue-50/40 via-white to-slate-50 shadow-2xs">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <ClipboardCheck className="h-4 w-4 text-blue-600" />
            My Care Plan & Actionable Next Steps
          </CardTitle>
          <Badge variant="outline" className="text-[10px] text-blue-700 border-blue-200">
            {tasks.length} Active {tasks.length === 1 ? "Item" : "Items"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 pt-0">
        {tasks.map((t) => (
          <div
            key={t.id}
            className="rounded-lg border border-slate-200/80 bg-white p-3 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2"
          >
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-slate-900">{t.title}</span>
                {t.priority === "urgent" && (
                  <Badge variant="destructive" className="text-[10px] py-0 px-1.5">
                    Urgent
                  </Badge>
                )}
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">{t.patient_instructions}</p>
            </div>
            {t.due_date && (
              <div className="text-[11px] text-slate-400 shrink-0 flex items-center gap-1">
                <Clock className="h-3 w-3" /> Due: {new Date(t.due_date).toLocaleDateString()}
              </div>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

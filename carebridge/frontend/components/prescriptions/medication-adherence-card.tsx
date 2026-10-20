"use client";

import * as React from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";
import { Pill, Check, X, Clock, Calendar } from "lucide-react";

interface TodayDose {
  prescription_item_id: string;
  prescription_id: string;
  drug_name: string;
  dosage: string;
  instructions: string;
  scheduled_time: string;
  status: "taken" | "skipped" | "late" | "missed" | "pending";
  log_id?: string;
  taken_at?: string;
}

interface AdherenceMetrics {
  patient_id: string;
  evaluation_window_days: number;
  total_scheduled_doses: number;
  taken_count: number;
  skipped_count: number;
  missed_count: number;
  adherence_percentage: number;
  rating_badge: string;
  rating_variant: "success" | "secondary" | "warning" | "destructive";
  today_schedule: TodayDose[];
}

interface MedicationAdherenceCardProps {
  patientId: string;
  refreshTrigger?: number;
}

export function MedicationAdherenceCard({
  patientId,
  refreshTrigger,
}: MedicationAdherenceCardProps) {
  const [metrics, setMetrics] = React.useState<AdherenceMetrics | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [actionLoading, setActionLoading] = React.useState<string | null>(null);

  const fetchAdherence = React.useCallback(async () => {
    try {
      const data = await apiFetch<AdherenceMetrics>(`/prescriptions/adherence/${patientId}`);
      if (data) {
        setMetrics(data);
      }
    } catch {
      // Graceful error fallback
    } finally {
      setLoading(false);
    }
  }, [patientId]);

  React.useEffect(() => {
    let ignore = false;
    async function load() {
      try {
        const data = await apiFetch<AdherenceMetrics>(`/prescriptions/adherence/${patientId}`);
        if (!ignore && data) {
          setMetrics(data);
        }
      } catch {
        // Fallback
      } finally {
        if (!ignore) setLoading(false);
      }
    }
    load();
    return () => {
      ignore = true;
    };
  }, [patientId, refreshTrigger]);

  const handleLogDose = async (dose: TodayDose, status: "taken" | "skipped") => {
    setActionLoading(dose.prescription_item_id);
    try {
      await apiFetch("/prescriptions/adherence/log", {
        method: "POST",
        body: JSON.stringify({
          prescription_item_id: dose.prescription_item_id,
          scheduled_time: dose.scheduled_time,
          status,
          notes: status === "taken" ? "Patient logged via CareBridge portal" : "Dose skipped by patient",
        }),
      });
      await fetchAdherence();
    } catch {
      // Graceful error
    } finally {
      setActionLoading(null);
    }
  };

  const getBadgeVariant = (variant: string) => {
    switch (variant) {
      case "success":
        return "bg-emerald-100 text-emerald-800 border-emerald-300";
      case "warning":
        return "bg-amber-100 text-amber-800 border-amber-300";
      case "destructive":
        return "bg-red-100 text-red-800 border-red-300";
      default:
        return "bg-blue-100 text-blue-800 border-blue-300";
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="py-6 text-center text-sm text-muted-foreground">
          Loading medication schedule & adherence metrics...
        </CardContent>
      </Card>
    );
  }

  if (!metrics) {
    return null;
  }

  return (
    <Card className="border-indigo-100 shadow-sm">
      <CardHeader className="pb-3 border-b bg-gradient-to-r from-indigo-50/50 to-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Pill className="w-5 h-5 text-indigo-600" />
            <div>
              <CardTitle className="text-base font-semibold">Medication Adherence</CardTitle>
              <p className="text-xs text-muted-foreground">Rolling 30-Day Compliance Tracker</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xl font-bold text-indigo-950">{metrics.adherence_percentage}%</span>
            <Badge variant="outline" className={getBadgeVariant(metrics.rating_variant)}>
              {metrics.rating_badge}
            </Badge>
          </div>
        </div>

        {/* Progress bar */}
        <div className="w-full bg-gray-100 rounded-full h-2 mt-3 overflow-hidden">
          <div
            className={`h-full transition-all duration-500 ${
              metrics.adherence_percentage >= 90
                ? "bg-emerald-500"
                : metrics.adherence_percentage >= 75
                ? "bg-blue-500"
                : metrics.adherence_percentage >= 50
                ? "bg-amber-500"
                : "bg-red-500"
            }`}
            style={{ width: `${metrics.adherence_percentage}%` }}
          />
        </div>

        <div className="grid grid-cols-3 gap-2 mt-2 pt-2 text-[11px] text-muted-foreground text-center">
          <div>
            <span className="font-semibold text-emerald-700">{metrics.taken_count}</span> Taken
          </div>
          <div>
            <span className="font-semibold text-amber-700">{metrics.skipped_count}</span> Skipped
          </div>
          <div>
            <span className="font-semibold text-red-700">{metrics.missed_count}</span> Missed
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-4 space-y-3">
        <div className="flex items-center justify-between text-xs font-semibold text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <Calendar className="w-3.5 h-3.5 text-indigo-600" />
            Today&apos;s Medication Schedule
          </div>
          <span className="text-[10px]">{metrics.today_schedule.length} scheduled</span>
        </div>

        {metrics.today_schedule.length === 0 ? (
          <div className="text-center py-4 text-xs text-muted-foreground bg-muted/20 rounded-md">
            No medication doses scheduled for today.
          </div>
        ) : (
          <div className="space-y-2">
            {metrics.today_schedule.map((dose, idx) => {
              const schedTime = new Date(dose.scheduled_time).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              });
              const isDone = dose.status === "taken" || dose.status === "late";
              const isSkipped = dose.status === "skipped";

              return (
                <div
                  key={idx}
                  className={`p-2.5 rounded-lg border text-xs flex items-center justify-between transition-colors ${
                    isDone
                      ? "bg-emerald-50/50 border-emerald-200 text-emerald-950"
                      : isSkipped
                      ? "bg-gray-50 border-gray-200 text-gray-500"
                      : "bg-white border-border hover:border-indigo-200"
                  }`}
                >
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">{dose.drug_name}</span>
                      <span className="text-muted-foreground">{dose.dosage}</span>
                    </div>
                    <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                      <span className="flex items-center gap-0.5 font-medium">
                        <Clock className="w-3 h-3" /> {schedTime}
                      </span>
                      <span>•</span>
                      <span>{dose.instructions}</span>
                    </div>
                  </div>

                  <div>
                    {isDone ? (
                      <Badge variant="outline" className="bg-emerald-100 text-emerald-800 text-[10px] gap-1">
                        <Check className="w-3 h-3" /> Taken
                      </Badge>
                    ) : isSkipped ? (
                      <Badge variant="outline" className="bg-gray-100 text-gray-700 text-[10px] gap-1">
                        <X className="w-3 h-3" /> Skipped
                      </Badge>
                    ) : (
                      <div className="flex items-center gap-1.5">
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={actionLoading === dose.prescription_item_id}
                          onClick={() => handleLogDose(dose, "skipped")}
                          className="h-7 px-2 text-[10px] text-muted-foreground hover:text-red-600"
                        >
                          Skip
                        </Button>
                        <Button
                          size="sm"
                          disabled={actionLoading === dose.prescription_item_id}
                          onClick={() => handleLogDose(dose, "taken")}
                          className="h-7 px-2.5 text-[10px] gap-1 bg-indigo-600 hover:bg-indigo-700 text-white"
                        >
                          <Check className="w-3 h-3" /> Mark Taken
                        </Button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

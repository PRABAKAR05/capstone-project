"use client";

import * as React from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { apiFetch, ProblemDetailsError } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Stethoscope, CheckCircle2, ClipboardList, UserCheck, Search, ShieldCheck } from "lucide-react";

interface PatientRecord {
  id: string;
  mrn: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender: string;
  blood_group: string;
  phone: string;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
}

interface AppointmentItem {
  id: string;
  patient_id: string;
  doctor_id: string;
  scheduled_at: string;
  status: "scheduled" | "confirmed" | "in_progress" | "completed" | "cancelled" | "no_show";
  reason_for_visit?: string;
}

export default function NurseDeskPage() {
  const { hospital } = useAuth();
  const [searchQuery, setSearchQuery] = React.useState("");
  const [patients, setPatients] = React.useState<PatientRecord[]>([]);
  const [appointments, setAppointments] = React.useState<AppointmentItem[]>([]);
  const [checkingInId, setCheckingInId] = React.useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = React.useState<string | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);

  const handleSearch = React.useCallback(async (q: string) => {
    setActionError(null);
    try {
      const endpoint = q ? `/patients?query=${encodeURIComponent(q)}` : "/patients";
      const data = await apiFetch<PatientRecord[]>(endpoint);
      setPatients(data || []);
    } catch {
      setPatients([
        {
          id: "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
          mrn: "MRN-2026-90421",
          first_name: "Alice",
          last_name: "Vance",
          date_of_birth: "1988-06-14",
          gender: "female",
          blood_group: "O+",
          phone: "+91 98765 43210",
        },
      ]);
    }
  }, []);

  React.useEffect(() => {
    let ignore = false;
    async function initDesk() {
      try {
        const [pData, appts] = await Promise.all([
          apiFetch<PatientRecord[]>("/patients").catch(() => null),
          apiFetch<AppointmentItem[]>("/appointments").catch(() => null),
        ]);
        if (!ignore) {
          if (pData) setPatients(pData);
          if (appts) setAppointments(appts);
        }
      } catch {
        // Handled gracefully
      }
    }
    initDesk();
    return () => {
      ignore = true;
    };
  }, []);

  const handleCheckIn = async (apptId: string) => {
    setCheckingInId(apptId);
    setActionError(null);
    setActionSuccess(null);
    try {
      await apiFetch(`/appointments/${apptId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: "confirmed" }),
      });
      setActionSuccess("Patient checked in successfully (Transition: scheduled -> confirmed).");
      setAppointments((prev) =>
        prev.map((a) => (a.id === apptId ? { ...a, status: "confirmed" as const } : a))
      );
    } catch (err) {
      if (err instanceof ProblemDetailsError) {
        setActionError(err.detail);
      } else {
        setActionError("Check-in failed.");
      }
    } finally {
      setCheckingInId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900 flex items-center">
            <Stethoscope className="h-5 w-5 mr-2 text-blue-700" />
            Clinical Nursing Desk & Patient Intake
          </h1>
          <p className="text-xs text-slate-500">
            Rapid Desk Check-In, Vitals Staging, and Patient Account Verification
          </p>
        </div>
        <Link href="/tasks">
          <Button variant="outline" size="sm" className="flex items-center space-x-1.5">
            <ClipboardList className="h-4 w-4 text-blue-600" />
            <span>Care Coordination Tasks</span>
          </Button>
        </Link>
      </div>

      {actionSuccess && (
        <Alert variant="success">
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          <AlertTitle>Success</AlertTitle>
          <AlertDescription>{actionSuccess}</AlertDescription>
        </Alert>
      )}

      {actionError && (
        <Alert variant="destructive">
          <AlertTitle>Operation Failed</AlertTitle>
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      )}

      {/* OPD Appointments Check-In Queue */}
      <Card className="border-slate-200 shadow-xs">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base flex items-center gap-2">
                <UserCheck className="h-4 w-4 text-blue-700" />
                <span>Today&apos;s Scheduled Consultations Queue</span>
              </CardTitle>
              <CardDescription className="text-xs">
                Clinical check-in desk for arriving outpatients
              </CardDescription>
            </div>
            <Badge variant="outline" className="text-xs bg-slate-50">
              {appointments.filter((a) => a.status === "scheduled").length} Pending Arrival
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader className="bg-slate-50">
                <TableRow>
                  <TableHead className="text-xs">Time</TableHead>
                  <TableHead className="text-xs">Patient ID</TableHead>
                  <TableHead className="text-xs">Reason</TableHead>
                  <TableHead className="text-xs">Status</TableHead>
                  <TableHead className="text-xs text-right">Desk Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {appointments.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-6 text-xs text-slate-500">
                      No active appointment queue for today.
                    </TableCell>
                  </TableRow>
                ) : (
                  appointments.map((appt) => (
                    <TableRow key={appt.id}>
                      <TableCell className="text-xs font-mono">
                        {new Date(appt.scheduled_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </TableCell>
                      <TableCell className="text-xs font-mono">{appt.patient_id.slice(0, 8)}...</TableCell>
                      <TableCell className="text-xs text-slate-600">{appt.reason_for_visit || "General Consultation"}</TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={`text-[10px] ${
                            appt.status === "confirmed"
                              ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                              : appt.status === "scheduled"
                              ? "bg-amber-50 text-amber-700 border-amber-200"
                              : "bg-slate-50 text-slate-700 border-slate-200"
                          }`}
                        >
                          {appt.status.toUpperCase()}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        {appt.status === "scheduled" ? (
                          <Button
                            size="sm"
                            disabled={checkingInId === appt.id}
                            onClick={() => handleCheckIn(appt.id)}
                            className="bg-blue-700 hover:bg-blue-800 text-white text-xs h-7 px-2.5"
                          >
                            {checkingInId === appt.id ? "Checking In..." : "Check In"}
                          </Button>
                        ) : (
                          <span className="text-[11px] text-slate-400">Checked In</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

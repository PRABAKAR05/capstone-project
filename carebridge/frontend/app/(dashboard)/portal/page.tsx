"use client";

import * as React from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { apiFetch, ProblemDetailsError } from "@/lib/api";
import { formatInHospitalTimezone } from "@/lib/timezone";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Calendar, User, HeartPulse, Phone, AlertCircle, CalendarPlus, XCircle, CheckCircle2 } from "lucide-react";
import { PatientSafetyAdvisory } from "@/components/conflicts/patient-safety-advisory";
import { PatientCarePlan } from "@/components/care-tasks/patient-care-plan";
import { MedicationAdherenceCard } from "@/components/prescriptions/medication-adherence-card";
import { PatientInsuranceCard } from "@/components/insurance/insurance-policy-card";

interface PatientData {
  id: string;
  mrn: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender: string;
  blood_group: string;
  phone: string;
  email?: string;
  address?: string;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
}

interface AppointmentData {
  id: string;
  doctor_id: string;
  department_id: string;
  scheduled_at: string;
  ends_at: string;
  status: "scheduled" | "confirmed" | "in_progress" | "completed" | "cancelled" | "no_show";
  reason_for_visit?: string;
  clinical_notes?: string;
}

export default function PatientPortalPage() {
  const { hospital } = useAuth();
  const [patient, setPatient] = React.useState<PatientData | null>(null);
  const [appointments, setAppointments] = React.useState<AppointmentData[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null);

  // Cancellation Modal state
  const [cancelModalOpen, setCancelModalOpen] = React.useState(false);
  const [selectedApptId, setSelectedApptId] = React.useState<string | null>(null);
  const [cancelReason, setCancelReason] = React.useState("");
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [cancelling, setCancelling] = React.useState(false);
  const [actionSuccess, setActionSuccess] = React.useState<string | null>(null);

  React.useEffect(() => {
    let ignore = false;
    async function loadData() {
      try {
        const patientId = "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
        const [pData, appts] = await Promise.all([
          apiFetch<PatientData>(`/patients/${patientId}`).catch(() => null),
          apiFetch<AppointmentData[]>(`/appointments?patient_id=${patientId}`).catch(() => []),
        ]);

        if (!ignore) {
          if (pData) {
            setPatient(pData);
          } else {
            setPatient({
              id: "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              mrn: "MRN-2026-90421",
              first_name: "Alice",
              last_name: "Vance",
              date_of_birth: "1988-06-14",
              gender: "female",
              blood_group: "O+",
              phone: "+91 98765 43210",
              emergency_contact_name: "Arthur Vance",
              emergency_contact_phone: "+91 98765 00000",
            });
          }
          setAppointments(appts || []);
          setLoading(false);
        }
      } catch {
        if (!ignore) setLoading(false);
      }
    }
    loadData();
    return () => {
      ignore = true;
    };
  }, [refreshKey]);

  const handleCancelSubmit = async () => {
    if (!selectedApptId || !cancelReason) return;
    setCancelling(true);
    setErrorMsg(null);
    try {
      await apiFetch(`/appointments/${selectedApptId}/status`, {
        method: "PATCH",
        body: JSON.stringify({
          status: "cancelled",
          cancellation_reason: cancelReason,
        }),
      });
      setActionSuccess("Appointment cancelled successfully.");
      setCancelModalOpen(false);
      setCancelReason("");
      setRefreshKey((k) => k + 1);
    } catch (err) {
      if (err instanceof ProblemDetailsError) {
        setErrorMsg(err.detail);
      } else {
        setErrorMsg("Failed to cancel appointment.");
      }
    } finally {
      setCancelling(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "confirmed":
        return <Badge variant="teal">Confirmed</Badge>;
      case "scheduled":
        return <Badge variant="default">Scheduled</Badge>;
      case "in_progress":
        return <Badge variant="warning">In Progress</Badge>;
      case "completed":
        return <Badge variant="success">Completed</Badge>;
      case "cancelled":
        return <Badge variant="destructive">Cancelled</Badge>;
      case "no_show":
        return <Badge variant="outline">No Show</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Title & Quick Action */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">
            Patient Health Portal
          </h1>
          <p className="text-xs text-slate-500">
            Authoritative Medical Record & Care Coordination Overview
          </p>
        </div>
        <Link href="/portal/book">
          <Button size="md" className="flex items-center space-x-1.5">
            <CalendarPlus className="h-4 w-4" />
            <span>Book New Appointment</span>
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

      {errorMsg && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4 text-red-600" />
          <AlertTitle>Notice</AlertTitle>
          <AlertDescription>{errorMsg}</AlertDescription>
        </Alert>
      )}

      {/* Patient Safety Advisory (Phase 7 CDS) */}
      <PatientSafetyAdvisory />

      {/* Patient Actionable Care Plan (Phase 8 Care Coordination) */}
      <PatientCarePlan />

      {/* Smart Medication Adherence (Phase 9) */}
      {patient?.id && <MedicationAdherenceCard patientId={patient.id} refreshTrigger={refreshKey} />}

      {/* Health Insurance & Pre-Auth Co-Pay Estimator (Phase 11) */}
      {patient?.id && <PatientInsuranceCard patientId={patient.id} />}


      {/* Patient Demographics Banner */}
      {loading ? (
        <Skeleton className="h-28 w-full rounded-xl" />
      ) : patient ? (
        <Card className="bg-gradient-to-r from-blue-50/60 via-white to-slate-50 border-blue-100">
          <CardContent className="p-5">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
              <div>
                <span className="text-[10px] font-semibold uppercase text-slate-400 block">
                  Patient Name
                </span>
                <span className="text-sm font-bold text-slate-900 flex items-center">
                  <User className="h-3.5 w-3.5 mr-1 text-blue-600" />
                  {patient.first_name} {patient.last_name}
                </span>
              </div>
              <div>
                <span className="text-[10px] font-semibold uppercase text-slate-400 block">
                  Hospital MRN
                </span>
                <span className="text-xs font-mono font-bold text-blue-800 bg-blue-100/60 px-2 py-0.5 rounded-md inline-block">
                  {patient.mrn}
                </span>
              </div>
              <div>
                <span className="text-[10px] font-semibold uppercase text-slate-400 block">
                  Date of Birth / Gender
                </span>
                <span className="text-xs font-semibold text-slate-800">
                  {patient.date_of_birth} ({patient.gender})
                </span>
              </div>
              <div>
                <span className="text-[10px] font-semibold uppercase text-slate-400 block">
                  Blood Group
                </span>
                <span className="text-xs font-bold text-red-700 flex items-center">
                  <HeartPulse className="h-3.5 w-3.5 mr-1 text-red-600" />
                  {patient.blood_group || "N/A"}
                </span>
              </div>
              <div>
                <span className="text-[10px] font-semibold uppercase text-slate-400 block">
                  Phone Number
                </span>
                <span className="text-xs font-semibold text-slate-800 flex items-center">
                  <Phone className="h-3 w-3 mr-1 text-slate-400" />
                  {patient.phone}
                </span>
              </div>
              <div>
                <span className="text-[10px] font-semibold uppercase text-slate-400 block">
                  Emergency Contact
                </span>
                <span className="text-xs font-medium text-slate-700 truncate block">
                  {patient.emergency_contact_name || "None Listed"}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {/* Upcoming & Past Appointments */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base flex items-center">
                <Calendar className="h-4 w-4 mr-2 text-blue-600" />
                Scheduled Clinical Consultations
              </CardTitle>
              <CardDescription>
                All consultation times are displayed in hospital timezone ({hospital?.timezone || "Asia/Kolkata"})
              </CardDescription>
            </div>
            <Badge variant="outline" className="text-xs">
              {appointments.length} Consultations
            </Badge>
          </div>
        </CardHeader>

        <CardContent>
          {loading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : appointments.length === 0 ? (
            <div className="text-center py-8 text-slate-500 space-y-2">
              <Calendar className="h-8 w-8 mx-auto text-slate-300" />
              <p className="text-xs">No appointments scheduled.</p>
              <Link href="/portal/book">
                <Button size="sm" variant="outline" className="mt-2 text-xs">
                  Book First Consultation
                </Button>
              </Link>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Scheduled Slot ({hospital?.timezone || "Asia/Kolkata"})</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Reason for Visit</TableHead>
                  <TableHead>Clinical Notes</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {appointments.map((appt) => {
                  const { fullStr } = formatInHospitalTimezone(appt.scheduled_at, hospital?.timezone);
                  const isCancellable = ["scheduled", "confirmed"].includes(appt.status);

                  return (
                    <TableRow key={appt.id}>
                      <TableCell className="font-semibold text-xs text-slate-900">
                        {fullStr}
                      </TableCell>
                      <TableCell>{getStatusBadge(appt.status)}</TableCell>
                      <TableCell className="text-xs text-slate-600">
                        {appt.reason_for_visit || "General Consultation"}
                      </TableCell>
                      <TableCell className="text-xs text-slate-500 italic">
                        {appt.clinical_notes || "—"}
                      </TableCell>
                      <TableCell className="text-right">
                        {isCancellable ? (
                          <Button
                            variant="destructive"
                            size="sm"
                            className="text-xs h-7 px-2"
                            onClick={() => {
                              setSelectedApptId(appt.id);
                              setCancelModalOpen(true);
                            }}
                          >
                            <XCircle className="h-3.5 w-3.5 mr-1" />
                            Cancel Slot
                          </Button>
                        ) : (
                          <span className="text-[11px] text-slate-400">Terminal</span>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Appointment Cancellation Dialog */}
      <Dialog open={cancelModalOpen} onOpenChange={setCancelModalOpen}>
        <DialogContent onClose={() => setCancelModalOpen(false)}>
          <DialogHeader>
            <DialogTitle>Confirm Appointment Cancellation</DialogTitle>
            <DialogDescription>
              In accordance with hospital policy, appointments may be cancelled up to 2 hours before the scheduled time.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-2">
            <Input
              label="Mandatory Reason for Cancellation"
              placeholder="e.g., Patient recovered, scheduling conflict"
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              required
            />
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCancelModalOpen(false)}
              disabled={cancelling}
            >
              Keep Appointment
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleCancelSubmit}
              isLoading={cancelling}
              disabled={!cancelReason.trim()}
            >
              Confirm Cancellation
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

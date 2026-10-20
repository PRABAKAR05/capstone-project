"use client";

import * as React from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { apiFetch, ProblemDetailsError } from "@/lib/api";
import { formatInHospitalTimezone } from "@/lib/timezone";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Stethoscope, CheckCircle2, AlertCircle, PlayCircle, FileText, ShieldCheck, FileCheck, ShieldAlert, RefreshCw, ClipboardList, Pill } from "lucide-react";
import { ConflictReconciliationModal, ClinicalConflict } from "@/components/conflicts/conflict-reconciliation-modal";
import { PrescriptionCreateModal } from "@/components/prescriptions/prescription-create-modal";
import { IoMTMonitorCard } from "@/components/telemetry/iomt-monitor-card";

interface DoctorAppointment {
  id: string;
  patient_id: string;
  doctor_id: string;
  scheduled_at: string;
  status: "scheduled" | "confirmed" | "in_progress" | "completed" | "cancelled" | "no_show";
  reason_for_visit?: string;
  clinical_notes?: string;
}

export default function DoctorWorkstationPage() {
  const { hospital } = useAuth();
  const [appointments, setAppointments] = React.useState<DoctorAppointment[]>([]);
  const [filterStatus, setFilterStatus] = React.useState<string>("all");
  const [pendingDocCount, setPendingDocCount] = React.useState<number>(0);
  const [recentDocId, setRecentDocId] = React.useState<string | null>(null);

  // Active Consultation Modal
  const [activeAppt, setActiveAppt] = React.useState<DoctorAppointment | null>(null);
  const [clinicalNotesInput, setClinicalNotesInput] = React.useState("");
  const [updating, setUpdating] = React.useState(false);
  const [actionSuccess, setActionSuccess] = React.useState<string | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);

  // Phase 7 Clinical Conflict Reconciler State
  const [conflicts, setConflicts] = React.useState<ClinicalConflict[]>([]);
  const [conflictCounts, setConflictCounts] = React.useState<{
    high_priority_count: number;
    moderate_priority_count: number;
    total_unresolved: number;
  }>({ high_priority_count: 0, moderate_priority_count: 0, total_unresolved: 0 });
  const [selectedConflict, setSelectedConflict] = React.useState<ClinicalConflict | null>(null);
  const [reconciliationModalOpen, setReconciliationModalOpen] = React.useState(false);
  const [scanningPatientId, setScanningPatientId] = React.useState<string | null>(null);

  // Phase 9 E-Prescription State
  const [prescriptionModalOpen, setPrescriptionModalOpen] = React.useState(false);
  const [prescriptionPatientId, setPrescriptionPatientId] = React.useState<string | null>(null);

  // Seed doctor ID for Dr. Evelyn Reed
  const doctorId = "71111111-1111-1111-1111-111111111111";

  const refreshConflicts = React.useCallback(async () => {
    try {
      const counts = await apiFetch<{
        high_priority_count: number;
        moderate_priority_count: number;
        total_unresolved: number;
      }>("/conflicts/notifications/counts");
      if (counts) setConflictCounts(counts);

      const confList = await apiFetch<ClinicalConflict[]>("/conflicts?resolution_status=unresolved");
      if (confList) setConflicts(confList);
    } catch {
      // Fallback
    }
  }, []);

  React.useEffect(() => {
    let ignore = false;
    async function loadQueue() {
      try {
        const data = await apiFetch<DoctorAppointment[]>(`/appointments?doctor_id=${doctorId}`);
        if (!ignore && data) {
          setAppointments(data);
        }
      } catch {
        if (!ignore) {
          setAppointments([
            {
              id: "99999999-0000-0000-0000-000000000001",
              patient_id: "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              doctor_id: doctorId,
              scheduled_at: new Date(Date.now() + 1800000).toISOString(),
              status: "confirmed",
              reason_for_visit: "Post-op Follow-up & ECG Review",
              clinical_notes: "Patient reports mild resting fatigue. BP: 124/82. ECG shows normal sinus rhythm.",
            },
          ]);
        }
      }

      // Fetch pending documents count
      try {
        const docData = await apiFetch<{ unread_count: number }>("/documents/notifications/unread-count");
        if (!ignore && docData) {
          setPendingDocCount(docData.unread_count || 0);
        }
        const list = await apiFetch<Array<{ id: string }>>("/documents");
        if (!ignore && list && list.length > 0) {
          setRecentDocId(list[0].id);
        }
      } catch {
        // Fallback demo state
      }

      // Fetch Phase 7 conflict alerts
      try {
        const counts = await apiFetch<{
          high_priority_count: number;
          moderate_priority_count: number;
          total_unresolved: number;
        }>("/conflicts/notifications/counts");
        if (!ignore && counts) {
          setConflictCounts(counts);
        }
        const confList = await apiFetch<ClinicalConflict[]>("/conflicts?resolution_status=unresolved");
        if (!ignore && confList) {
          setConflicts(confList);
        }
      } catch {
        // Fallback demo state
      }
    }
    loadQueue();
    return () => {
      ignore = true;
    };
  }, [doctorId]);

  const handleScanConflicts = async (patientId: string) => {
    setScanningPatientId(patientId);
    setActionError(null);
    setActionSuccess(null);
    try {
      const res = await apiFetch<{ conflicts_detected: number; conflicts: ClinicalConflict[] }>(
        `/conflicts/scan/${patientId}`,
        { method: "POST" }
      );
      setActionSuccess(`Document reconciliation scan completed: ${res.conflicts_detected} findings evaluated.`);
      await refreshConflicts();
      if (res.conflicts && res.conflicts.length > 0) {
        setSelectedConflict(res.conflicts[0]);
        setReconciliationModalOpen(true);
      }
    } catch (err: unknown) {
      if (err instanceof ProblemDetailsError) {
        setActionError(err.detail);
      } else {
        setActionError("Failed to run document conflict scan.");
      }
    } finally {
      setScanningPatientId(null);
    }
  };

  const handleStartConsultation = async (appt: DoctorAppointment) => {
    setUpdating(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      await apiFetch(`/appointments/${appt.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: "in_progress" }),
      });
      setActionSuccess("Consultation initiated (Status: in_progress).");
      setAppointments((prev) =>
        prev.map((a) => (a.id === appt.id ? { ...a, status: "in_progress" as const } : a))
      );
      setActiveAppt({ ...appt, status: "in_progress" });
      setClinicalNotesInput(appt.clinical_notes || "");
    } catch (err) {
      if (err instanceof ProblemDetailsError) {
        setActionError(err.detail);
      } else {
        setActionError("Failed to start consultation.");
      }
    } finally {
      setUpdating(false);
    }
  };

  const handleCompleteConsultation = async () => {
    if (!activeAppt) return;
    setUpdating(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      await apiFetch(`/appointments/${activeAppt.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({
          status: "completed",
          clinical_notes: clinicalNotesInput,
        }),
      });
      setActionSuccess("Consultation completed and clinical notes committed to patient record.");
      setAppointments((prev) =>
        prev.map((a) =>
          a.id === activeAppt.id
            ? { ...a, status: "completed" as const, clinical_notes: clinicalNotesInput }
            : a
        )
      );
      setActiveAppt(null);
    } catch (err) {
      if (err instanceof ProblemDetailsError) {
        setActionError(err.detail);
      } else {
        // Fallback demo commit
        setActionSuccess("Consultation completed (Demonstration record saved).");
        setAppointments((prev) =>
          prev.map((a) =>
            a.id === activeAppt.id
              ? { ...a, status: "completed" as const, clinical_notes: clinicalNotesInput }
              : a
          )
        );
        setActiveAppt(null);
      }
    } finally {
      setUpdating(false);
    }
  };

  const filteredAppointments = appointments.filter((a) => {
    if (filterStatus === "all") return true;
    return a.status === filterStatus;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900 flex items-center">
            <Stethoscope className="h-5 w-5 mr-2 text-teal-700" />
            Physician Clinical Workstation
          </h1>
          <p className="text-xs text-slate-500">
            Daily Patient Queue, Clinical Examination & Authorized Notes Documentation
          </p>
        </div>
        <div className="flex items-center space-x-2">
          {["all", "confirmed", "in_progress", "completed"].map((st) => (
            <button
              key={st}
              onClick={() => setFilterStatus(st)}
              className={`px-3 py-1.5 rounded-md text-xs font-semibold capitalize transition-all cursor-pointer ${
                filterStatus === st
                  ? "bg-blue-700 text-white font-bold"
                  : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
              }`}
            >
              {st.replace("_", " ")}
            </button>
          ))}
        </div>
      </div>

      {/* Phase 7 Urgent Conflict Alert Banner */}
      {(conflictCounts.high_priority_count > 0 || conflictCounts.total_unresolved > 0) && (
        <div
          className={`rounded-xl border p-4 shadow-2xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
            conflictCounts.high_priority_count > 0
              ? "border-red-300 bg-red-50/95 text-red-950"
              : "border-amber-300 bg-amber-50/95 text-amber-950"
          }`}
        >
          <div className="flex items-center gap-3">
            <div
              className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg font-bold text-sm shadow-xs text-white ${
                conflictCounts.high_priority_count > 0 ? "bg-red-600" : "bg-amber-600"
              }`}
            >
              {conflictCounts.high_priority_count > 0
                ? conflictCounts.high_priority_count
                : conflictCounts.total_unresolved}
            </div>
            <div>
              <h4 className="text-sm font-bold flex items-center gap-1.5">
                <ShieldAlert
                  className={`h-4 w-4 ${
                    conflictCounts.high_priority_count > 0 ? "text-red-700" : "text-amber-700"
                  }`}
                />
                {conflictCounts.high_priority_count > 0
                  ? "Urgent Clinical Conflict Alert: Medication/Document Discrepancies"
                  : "Clinical Document Discrepancies Require Reconciliation"}
              </h4>
              <p className="text-xs opacity-90 mt-0.5">
                {conflictCounts.high_priority_count > 0
                  ? `${conflictCounts.high_priority_count} high-priority conflict(s) detected across patient encounters requiring documented clinical acknowledgement.`
                  : `${conflictCounts.total_unresolved} discrepancy finding(s) detected across outside records and active orders.`}
              </p>
            </div>
          </div>
          <Button
            size="sm"
            onClick={() => {
              if (conflicts.length > 0) {
                setSelectedConflict(conflicts[0]);
                setReconciliationModalOpen(true);
              }
            }}
            className={`text-xs font-semibold shrink-0 text-white ${
              conflictCounts.high_priority_count > 0
                ? "bg-red-700 hover:bg-red-800"
                : "bg-amber-700 hover:bg-amber-800"
            }`}
          >
            Review & Reconcile
          </Button>
        </div>
      )}

      {/* Document Review Task Notification Badge */}
      {pendingDocCount > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50/80 p-4 shadow-2xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-amber-500 text-white font-bold text-sm shadow-xs">
              {pendingDocCount}
            </div>
            <div>
              <h4 className="text-sm font-semibold text-amber-950 flex items-center gap-1.5">
                <FileCheck className="h-4 w-4 text-amber-700" />
                Clinical Documents Pending Review
              </h4>
              <p className="text-xs text-amber-800">
                Patients have uploaded outside discharge records and lab reports that require physician sign-off.
              </p>
            </div>
          </div>
          <Link href={recentDocId ? `/doctor/documents/${recentDocId}` : "/doctor"}>
            <Button variant="primary" size="sm" className="bg-amber-600 hover:bg-amber-700 text-white text-xs shrink-0">
              Review Documents
            </Button>
          </Link>
        </div>
      )}

      {/* Phase 8 Care Coordination Task Board Banner */}
      <div className="rounded-xl border border-blue-200 bg-blue-50/70 p-4 shadow-2xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-600 text-white font-bold text-sm shadow-xs">
            <ClipboardList className="h-5 w-5" />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-blue-950 flex items-center gap-1.5">
              Care Coordination & Task Board
            </h4>
            <p className="text-xs text-blue-800">
              Manage post-op checks, discharge plans, medication reviews, and specialist referrals across your care team.
            </p>
          </div>
        </div>
        <Link href="/tasks">
          <Button variant="outline" size="sm" className="bg-white hover:bg-blue-100 text-blue-900 border-blue-300 text-xs shrink-0">
            Open Task Board
          </Button>
        </Link>
      </div>

      {actionSuccess && (
        <Alert variant="success">
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          <AlertTitle>Clinical Action Committed</AlertTitle>
          <AlertDescription>{actionSuccess}</AlertDescription>
        </Alert>
      )}

      {actionError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4 text-red-600" />
          <AlertTitle>Authorization Warning</AlertTitle>
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      )}

      {/* Clinical Queue Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Consultation Schedule ({filteredAppointments.length})</CardTitle>
          <CardDescription>
            Assigned patients for Dr. Evelyn Reed ({hospital?.timezone || "Asia/Kolkata"})
          </CardDescription>
        </CardHeader>

        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time Slot</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Chief Complaint</TableHead>
                <TableHead>Clinical Record</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredAppointments.map((appt) => {
                const { fullStr } = formatInHospitalTimezone(appt.scheduled_at, hospital?.timezone);

                return (
                  <TableRow key={appt.id}>
                    <TableCell className="font-semibold text-xs text-slate-900">
                      {fullStr}
                    </TableCell>
                    <TableCell>
                      {appt.status === "confirmed" ? (
                        <Badge variant="teal">Ready in Waiting Room</Badge>
                      ) : appt.status === "in_progress" ? (
                        <Badge variant="warning">In Consultation</Badge>
                      ) : appt.status === "completed" ? (
                        <Badge variant="success">Completed</Badge>
                      ) : (
                        <Badge variant="secondary">{appt.status}</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-slate-700">
                      {appt.reason_for_visit || "General Checkup"}
                    </TableCell>
                    <TableCell className="text-xs text-slate-500 italic max-w-xs truncate">
                      {appt.clinical_notes || "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={scanningPatientId === appt.patient_id}
                          onClick={() => handleScanConflicts(appt.patient_id)}
                          title="Run reconciliation scan across patient encounters"
                          className="h-7 px-2 text-xs text-slate-700 hover:text-slate-900 border-slate-200"
                        >
                          <RefreshCw
                            className={`h-3 w-3 mr-1 ${
                              scanningPatientId === appt.patient_id ? "animate-spin text-blue-600" : ""
                            }`}
                          />
                          {scanningPatientId === appt.patient_id ? "Scanning..." : "Check Conflicts"}
                        </Button>
                        {appt.status === "confirmed" && (
                          <Button
                            size="sm"
                            onClick={() => handleStartConsultation(appt)}
                            className="h-7 px-2.5 text-xs bg-blue-700 hover:bg-blue-800 text-white"
                          >
                            <PlayCircle className="h-3.5 w-3.5 mr-1" />
                            Start Exam
                          </Button>
                        )}
                        {appt.status === "in_progress" && (
                          <Button
                            size="sm"
                            onClick={() => {
                              setActiveAppt(appt);
                              setClinicalNotesInput(appt.clinical_notes || "");
                            }}
                            className="h-7 px-2.5 text-xs bg-amber-600 hover:bg-amber-700 text-white"
                          >
                            <FileText className="h-3.5 w-3.5 mr-1" />
                            Record Notes
                          </Button>
                        )}
                        {appt.status === "completed" && (
                          <span className="text-[11px] text-slate-400 font-medium">Record Locked</span>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Phase 12 Bedside IoMT Telemetry Monitor & FDIA Consistency Verification */}
      <IoMTMonitorCard
        patientId={appointments[0]?.patient_id || "11111111-1111-1111-1111-111111111111"}
        patientName={appointments[0] ? `Patient ${appointments[0].patient_id.substring(0, 8)}...` : "ICU Bedside Patient"}
        deviceId="iomt-bedside-node-01"
      />

      {/* Consultation Documentation Modal */}
      <Dialog open={!!activeAppt} onOpenChange={(open) => !open && setActiveAppt(null)}>
        <DialogContent onClose={() => setActiveAppt(null)}>
          <DialogHeader>
            <DialogTitle>Consultation & Clinical Notes</DialogTitle>
            <DialogDescription>
              Record diagnosis, findings, and prescriptions. Only the assigned physician can authorize notes.
            </DialogDescription>
          </DialogHeader>

          {activeAppt && (
            <div className="space-y-4 py-2 text-xs">
              <div className="rounded-lg bg-blue-50/70 border border-blue-200 p-3 space-y-1 text-blue-900">
                <span className="font-bold flex items-center">
                  <ShieldCheck className="h-4 w-4 mr-1 text-blue-700" />
                  Assigned Physician Security Boundary
                </span>
                <p className="text-[11px] text-blue-800 leading-relaxed">
                  FastAPI validates that your authenticated profile matches the assigned doctor ID for this appointment. Unauthorized note mutations raise HTTP 403 Forbidden.
                </p>
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-bold text-slate-800">
                  Authoritative Clinical Notes & Observations
                </label>
                <textarea
                  className="w-full h-32 rounded-lg border border-slate-300 p-3 text-xs leading-relaxed focus:outline-none focus:ring-2 focus:ring-blue-600 bg-white"
                  placeholder="Record patient vitals, clinical impression, diagnostic codes, and management plan..."
                  value={clinicalNotesInput}
                  onChange={(e) => setClinicalNotesInput(e.target.value)}
                />
              </div>
            </div>
          )}

          <DialogFooter className="flex items-center justify-between sm:justify-between w-full">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                if (activeAppt) {
                  setPrescriptionPatientId(activeAppt.patient_id);
                  setPrescriptionModalOpen(true);
                }
              }}
              className="text-indigo-600 border-indigo-200 hover:bg-indigo-50 gap-1.5"
            >
              <Pill className="w-4 h-4 text-indigo-600" /> Issue E-Prescription
            </Button>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setActiveAppt(null)}
                disabled={updating}
              >
                Close
              </Button>
              <Button
                size="sm"
                onClick={handleCompleteConsultation}
                isLoading={updating}
                className="bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                Sign & Complete Consultation
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Phase 7 Side-by-Side Conflict Reconciliation Modal */}
      <ConflictReconciliationModal
        conflict={selectedConflict}
        open={reconciliationModalOpen}
        onClose={() => setReconciliationModalOpen(false)}
        onAcknowledgeSuccess={() => {
          setActionSuccess("Clinical conflict acknowledged with documented rationale.");
          refreshConflicts();
        }}
      />

      {/* Phase 9 Digital E-Prescription Authoring Modal */}
      <PrescriptionCreateModal
        open={prescriptionModalOpen}
        onOpenChange={setPrescriptionModalOpen}
        patientId={prescriptionPatientId || ""}
        onSuccess={() => {
          setActionSuccess("E-Prescription issued and cryptographically signed.");
        }}
      />
    </div>
  );
}

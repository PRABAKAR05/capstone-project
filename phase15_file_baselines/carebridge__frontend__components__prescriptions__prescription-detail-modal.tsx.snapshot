"use client";

import * as React from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { apiFetch } from "@/lib/api";
import { QrCode, CheckCircle2, ShieldCheck, XCircle, PackageCheck, AlertTriangle } from "lucide-react";

interface PrescriptionItem {
  id: string;
  drug_name: string;
  dosage: string;
  frequency: string;
  route: string;
  duration_days: number;
  instructions: string;
}

interface PrescriptionDetail {
  id: string;
  patient_id: string;
  doctor_id: string;
  status: string;
  diagnosis_context?: string;
  notes?: string;
  discontinuation_rationale?: string;
  verification_hash: string;
  issued_at: string;
  valid_until: string;
  dispensed_at?: string;
  dispensing_notes?: string;
  items: PrescriptionItem[];
}

interface PrescriptionDetailModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  prescriptionId: string | null;
  userRole?: string;
  onUpdate?: () => void;
}

export function PrescriptionDetailModal({
  open,
  onOpenChange,
  prescriptionId,
  userRole,
  onUpdate,
}: PrescriptionDetailModalProps) {
  const [prescription, setPrescription] = React.useState<PrescriptionDetail | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Dispensing state
  const [dispensingNotes, setDispensingNotes] = React.useState("");
  const [actionLoading, setActionLoading] = React.useState(false);

  // Discontinue state
  const [discontinuing, setDiscontinuing] = React.useState(false);
  const [rationale, setRationale] = React.useState("");

  React.useEffect(() => {
    if (!open || !prescriptionId) return;
    let ignore = false;

    async function fetchDetail() {
      setLoading(true);
      setError(null);
      try {
        const data = await apiFetch<PrescriptionDetail>(`/prescriptions/${prescriptionId}`);
        if (!ignore && data) {
          setPrescription(data);
        }
      } catch (err: unknown) {
        if (!ignore) {
          const msg = err instanceof Error ? err.message : "Failed to load prescription";
          setError(msg);
        }
      } finally {
        if (!ignore) setLoading(false);
      }
    }

    fetchDetail();
    return () => {
      ignore = true;
    };
  }, [open, prescriptionId]);

  const handleDispense = async (targetStatus: "ready_for_pickup" | "dispensed") => {
    if (!prescriptionId) return;
    setActionLoading(true);
    setError(null);
    try {
      await apiFetch(`/prescriptions/${prescriptionId}/dispense`, {
        method: "POST",
        body: JSON.stringify({
          status: targetStatus,
          dispensing_notes: dispensingNotes || undefined,
        }),
      });
      onUpdate?.();
      onOpenChange(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update dispensing status";
      setError(msg);
    } finally {
      setActionLoading(false);
    }
  };

  const handleDiscontinue = async () => {
    if (!prescriptionId) return;
    if (rationale.trim().length < 10) {
      setError("Please document a clinical rationale of at least 10 characters.");
      return;
    }

    setActionLoading(true);
    setError(null);
    try {
      await apiFetch(`/prescriptions/${prescriptionId}/discontinue`, {
        method: "POST",
        body: JSON.stringify({ rationale: rationale.trim() }),
      });
      onUpdate?.();
      onOpenChange(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to discontinue prescription";
      setError(msg);
    } finally {
      setActionLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "prescribed":
        return <Badge variant="secondary" className="bg-blue-100 text-blue-800">Prescribed</Badge>;
      case "ready_for_pickup":
        return <Badge variant="secondary" className="bg-amber-100 text-amber-800">Ready for Pickup</Badge>;
      case "dispensed":
        return <Badge variant="secondary" className="bg-emerald-100 text-emerald-800">Dispensed</Badge>;
      case "completed":
        return <Badge variant="secondary" className="bg-gray-100 text-gray-800">Completed</Badge>;
      case "discontinued":
        return <Badge variant="destructive">Discontinued</Badge>;
      default:
        return <Badge>{status}</Badge>;
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-indigo-600" />
              <DialogTitle>Digital Prescription Record</DialogTitle>
            </div>
            {prescription && getStatusBadge(prescription.status)}
          </div>
          <DialogDescription>
            Tamper-evident clinical order with cryptographic HMAC authentication.
          </DialogDescription>
        </DialogHeader>

        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {loading ? (
          <div className="py-8 text-center text-sm text-muted-foreground">Loading prescription details...</div>
        ) : prescription ? (
          <div className="space-y-4 py-2 text-xs">
            {/* Clinical context */}
            <div className="p-3 bg-muted/30 rounded-lg space-y-1">
              {prescription.diagnosis_context && (
                <div>
                  <span className="font-semibold text-muted-foreground">Diagnosis: </span>
                  <span className="font-medium text-foreground">{prescription.diagnosis_context}</span>
                </div>
              )}
              {prescription.notes && (
                <div>
                  <span className="font-semibold text-muted-foreground">Physician Instructions: </span>
                  <span className="text-foreground">{prescription.notes}</span>
                </div>
              )}
              {prescription.discontinuation_rationale && (
                <div className="text-red-700 bg-red-50 p-2 rounded mt-1 border border-red-200">
                  <span className="font-semibold">Discontinuation Rationale: </span>
                  {prescription.discontinuation_rationale}
                </div>
              )}
            </div>

            {/* Prescribed Items Table */}
            <div>
              <h4 className="font-semibold text-sm mb-2">Prescribed Items ({prescription.items?.length || 0})</h4>
              <div className="border rounded-md divide-y">
                {prescription.items?.map((item) => (
                  <div key={item.id} className="p-3 flex items-start justify-between">
                    <div>
                      <div className="font-semibold text-sm text-foreground">{item.drug_name}</div>
                      <div className="text-muted-foreground">
                        {item.dosage} • {item.frequency} • {item.route} • {item.duration_days} days
                      </div>
                      <div className="text-xs text-indigo-700 mt-0.5">{item.instructions}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Verification / Tamper-evident Card */}
            <div className="p-3 bg-indigo-50/50 rounded-lg border border-indigo-100 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 font-semibold text-indigo-950">
                  <QrCode className="w-4 h-4 text-indigo-600" />
                  Cryptographic Verification Seal
                </div>
                <span className="text-[10px] text-muted-foreground">
                  Valid Until: {new Date(prescription.valid_until).toLocaleDateString()}
                </span>
              </div>
              <p className="font-mono text-[10px] text-indigo-800 break-all bg-white/80 p-1.5 rounded border border-indigo-200">
                {prescription.verification_hash}
              </p>
              <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                <span>Issued: {new Date(prescription.issued_at).toLocaleString()}</span>
                <a
                  href={`/verify-prescription/${encodeURIComponent(prescription.verification_hash)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-indigo-600 hover:underline font-semibold"
                >
                  Verify Authenticity &rarr;
                </a>
              </div>
            </div>

            {/* Discontinuation Section (Doctor Only) */}
            {discontinuing ? (
              <div className="p-3 bg-red-50 rounded-lg border border-red-200 space-y-2">
                <div className="flex items-center gap-1.5 font-semibold text-red-900 text-xs">
                  <AlertTriangle className="w-4 h-4 text-red-600" />
                  Document Discontinuation Rationale
                </div>
                <Input
                  placeholder="Mandatory clinical rationale (e.g. drug intolerance, regimen update)..."
                  value={rationale}
                  onChange={(e) => setRationale(e.target.value)}
                  className="text-xs h-8 bg-white"
                />
                <div className="flex items-center justify-end gap-2 pt-1">
                  <Button type="button" variant="ghost" size="sm" onClick={() => setDiscontinuing(false)}>
                    Cancel
                  </Button>
                  <Button
                    type="button"
                    variant="destructive"
                    size="sm"
                    disabled={actionLoading}
                    onClick={handleDiscontinue}
                  >
                    Confirm Discontinuation
                  </Button>
                </div>
              </div>
            ) : null}

            {/* Dispensing Actions for Staff */}
            {prescription.status !== "discontinued" && prescription.status !== "completed" && (
              <div className="pt-2 flex flex-wrap items-center justify-between gap-2 border-t">
                {userRole === "doctor" && !discontinuing && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setDiscontinuing(true)}
                    className="text-red-600 hover:text-red-700 hover:bg-red-50 text-xs gap-1"
                  >
                    <XCircle className="w-3.5 h-3.5" /> Discontinue
                  </Button>
                )}

                {userRole !== "patient" && userRole !== "caregiver" && (
                  <div className="flex flex-col sm:flex-row items-end sm:items-center gap-2 ml-auto w-full sm:w-auto">
                    <Input
                      placeholder="Optional batch / lot notes..."
                      value={dispensingNotes}
                      onChange={(e) => setDispensingNotes(e.target.value)}
                      className="text-xs h-7 w-full sm:w-48 bg-white"
                    />
                    {prescription.status === "prescribed" && (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={actionLoading}
                        onClick={() => handleDispense("ready_for_pickup")}
                        className="text-xs gap-1 whitespace-nowrap"
                      >
                        <PackageCheck className="w-3.5 h-3.5" /> Ready for Pickup
                      </Button>
                    )}
                    {prescription.status !== "dispensed" && (
                      <Button
                        type="button"
                        size="sm"
                        disabled={actionLoading}
                        onClick={() => handleDispense("dispensed")}
                        className="text-xs gap-1 bg-emerald-600 hover:bg-emerald-700"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" /> Mark Dispensed
                      </Button>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        ) : null}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

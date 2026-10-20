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
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { apiFetch } from "@/lib/api";
import { Plus, Trash2, ShieldAlert, CheckCircle2, Lock } from "lucide-react";

interface PrescriptionItemInput {
  drug_name: string;
  dosage: string;
  frequency: string;
  route: string;
  duration_days: number;
  instructions: string;
  refills_remaining: number;
}

interface SafetyConflict {
  conflict_type: string;
  severity: string;
  title: string;
  description: string;
  patient_advisory: string;
  involved_drugs: string[];
}

interface SafetyAdvisory {
  has_conflicts: boolean;
  max_severity: string;
  conflicts_count: number;
  conflicts: SafetyConflict[];
  advisory_summary: string;
}

interface PrescriptionCreateModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  patientId: string;
  patientName?: string;
  onSuccess?: () => void;
}

export function PrescriptionCreateModal({
  open,
  onOpenChange,
  patientId,
  patientName,
  onSuccess,
}: PrescriptionCreateModalProps) {
  const [diagnosisContext, setDiagnosisContext] = React.useState("");
  const [notes, setNotes] = React.useState("");
  const [items, setItems] = React.useState<PrescriptionItemInput[]>([
    {
      drug_name: "",
      dosage: "",
      frequency: "Once daily",
      route: "oral",
      duration_days: 30,
      instructions: "Take with food",
      refills_remaining: 0,
    },
  ]);

  const [submitting, setSubmitting] = React.useState(false);
  const [safetyAdvisory, setSafetyAdvisory] = React.useState<SafetyAdvisory | null>(null);
  const [acknowledged, setAcknowledged] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const addItem = () => {
    setItems((prev) => [
      ...prev,
      {
        drug_name: "",
        dosage: "",
        frequency: "Once daily",
        route: "oral",
        duration_days: 30,
        instructions: "Take with food",
        refills_remaining: 0,
      },
    ]);
  };

  const removeItem = (idx: number) => {
    if (items.length <= 1) return;
    setItems((prev) => prev.filter((_, i) => i !== idx));
  };

  const updateItem = (idx: number, field: keyof PrescriptionItemInput, val: unknown) => {
    setItems((prev) =>
      prev.map((item, i) => (i === idx ? { ...item, [field]: val } : item))
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation
    for (const it of items) {
      if (!it.drug_name.trim() || !it.dosage.trim()) {
        setError("All medication items must specify a drug name and dosage.");
        return;
      }
    }

    if (safetyAdvisory?.has_conflicts && !acknowledged) {
      setError("Please acknowledge the clinical decision support safety findings before signing.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await apiFetch<{ id: string; verification_hash: string; safety_advisory?: SafetyAdvisory }>(
        "/prescriptions",
        {
          method: "POST",
          body: JSON.stringify({
            patient_id: patientId,
            diagnosis_context: diagnosisContext,
            notes,
            items,
          }),
        }
      );

      if (res?.safety_advisory?.has_conflicts && !acknowledged) {
        setSafetyAdvisory(res.safety_advisory);
        setSubmitting(false);
        return;
      }

      onSuccess?.();
      onOpenChange(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to issue prescription";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <Lock className="w-5 h-5 text-indigo-600" />
            <DialogTitle>Author Digital Prescription</DialogTitle>
          </div>
          <DialogDescription>
            Generate a tamper-evident, cryptographically signed e-prescription
            {patientName ? ` for ${patientName}` : ""}.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 py-2">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {safetyAdvisory?.has_conflicts && (
            <Alert variant="destructive" className="border-red-500 bg-red-50 text-red-900">
              <ShieldAlert className="w-5 h-5 text-red-600" />
              <AlertTitle className="font-semibold text-red-800">
                Clinical Safety Advisory: {safetyAdvisory.max_severity.toUpperCase()} Priority Conflict
              </AlertTitle>
              <AlertDescription className="space-y-2 mt-2">
                <p className="text-xs">{safetyAdvisory.advisory_summary}</p>
                <div className="space-y-1.5">
                  {safetyAdvisory.conflicts.map((c, i) => (
                    <div key={i} className="text-xs bg-white/80 p-2 rounded border border-red-200">
                      <span className="font-semibold text-red-700">{c.title}:</span> {c.description}
                    </div>
                  ))}
                </div>
                <label className="flex items-center gap-2 mt-2 pt-2 border-t border-red-200 text-xs font-medium cursor-pointer">
                  <input
                    type="checkbox"
                    checked={acknowledged}
                    onChange={(e) => setAcknowledged(e.target.checked)}
                    className="rounded border-gray-300 text-indigo-600"
                  />
                  I have clinically reviewed these conflict advisories and confirm this prescription order.
                </label>
              </AlertDescription>
            </Alert>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-muted-foreground">Clinical Diagnosis Context</label>
              <Input
                placeholder="e.g. Type 2 Diabetes, Hypertension"
                value={diagnosisContext}
                onChange={(e) => setDiagnosisContext(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-muted-foreground">Physician Instructions / Notes</label>
              <Input
                placeholder="e.g. Take with breakfast; monitor glucose daily"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-semibold">Prescribed Medications</h4>
              <Button type="button" variant="outline" size="sm" onClick={addItem} className="h-7 text-xs gap-1">
                <Plus className="w-3.5 h-3.5" /> Add Drug
              </Button>
            </div>

            {items.map((item, idx) => (
              <div key={idx} className="p-3 bg-muted/30 rounded-lg border space-y-2 text-xs relative">
                <div className="flex items-center justify-between pb-1 border-b">
                  <span className="font-semibold text-foreground">Item #{idx + 1}</span>
                  {items.length > 1 && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => removeItem(idx)}
                      className="h-6 w-6 p-0 text-red-500 hover:text-red-700 hover:bg-red-50"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  )}
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  <div className="col-span-2">
                    <label className="text-[10px] text-muted-foreground">Drug Name</label>
                    <Input
                      className="h-7 text-xs"
                      placeholder="e.g. Metformin"
                      value={item.drug_name}
                      onChange={(e) => updateItem(idx, "drug_name", e.target.value)}
                      required
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-muted-foreground">Dosage</label>
                    <Input
                      className="h-7 text-xs"
                      placeholder="e.g. 500 mg"
                      value={item.dosage}
                      onChange={(e) => updateItem(idx, "dosage", e.target.value)}
                      required
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-muted-foreground">Route</label>
                    <Input
                      className="h-7 text-xs"
                      placeholder="oral"
                      value={item.route}
                      onChange={(e) => updateItem(idx, "route", e.target.value)}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  <div>
                    <label className="text-[10px] text-muted-foreground">Frequency</label>
                    <Input
                      className="h-7 text-xs"
                      placeholder="e.g. Twice daily"
                      value={item.frequency}
                      onChange={(e) => updateItem(idx, "frequency", e.target.value)}
                      required
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-muted-foreground">Duration (Days)</label>
                    <Input
                      type="number"
                      min={1}
                      className="h-7 text-xs"
                      value={item.duration_days}
                      onChange={(e) => updateItem(idx, "duration_days", parseInt(e.target.value) || 30)}
                      required
                    />
                  </div>
                  <div className="col-span-2">
                    <label className="text-[10px] text-muted-foreground">Instructions</label>
                    <Input
                      className="h-7 text-xs"
                      placeholder="e.g. Take with food after meals"
                      value={item.instructions}
                      onChange={(e) => updateItem(idx, "instructions", e.target.value)}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>

          <DialogFooter className="pt-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting} className="gap-2 bg-indigo-600 hover:bg-indigo-700">
              {submitting ? (
                "Signing & Issuing..."
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" /> Sign & Issue E-Prescription
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

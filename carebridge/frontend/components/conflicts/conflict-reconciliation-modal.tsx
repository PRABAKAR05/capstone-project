"use client";

import * as React from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { apiFetch, ProblemDetailsError } from "@/lib/api";
import { ShieldAlert, AlertTriangle, FileText, CheckCircle2, Info } from "lucide-react";

export interface ConflictSource {
  id: string;
  role_in_conflict: string;
  citation_text: string;
  document_id?: string;
  entity_id?: string;
  created_at: string;
}

export interface ClinicalConflict {
  id: string;
  hospital_id: string;
  patient_id: string;
  conflict_type: string;
  review_priority: "high" | "moderate" | "low";
  title: string;
  clinical_summary?: string;
  patient_friendly_summary: string;
  resolution_status: "unresolved" | "acknowledged_with_rationale" | "resolved_via_order_change";
  acknowledged_by?: string;
  acknowledged_at?: string;
  clinician_rationale?: string;
  created_at: string;
  updated_at: string;
  sources?: ConflictSource[];
}

interface ConflictReconciliationModalProps {
  conflict: ClinicalConflict | null;
  open: boolean;
  onClose: () => void;
  onAcknowledgeSuccess: (updated: ClinicalConflict) => void;
}

function ConflictDialogBody({
  conflict,
  onClose,
  onAcknowledgeSuccess,
}: {
  conflict: ClinicalConflict;
  onClose: () => void;
  onAcknowledgeSuccess: (updated: ClinicalConflict) => void;
}) {
  const [rationale, setRationale] = React.useState(conflict.clinician_rationale || "");
  const [submitting, setSubmitting] = React.useState(false);
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null);

  const isAcknowledged = conflict.resolution_status === "acknowledged_with_rationale";

  const handleAcknowledge = async () => {
    if (rationale.trim().length < 10) {
      setErrorMsg("Please provide at least 10 characters documenting your clinical rationale.");
      return;
    }
    setSubmitting(true);
    setErrorMsg(null);
    try {
      const updated = await apiFetch<ClinicalConflict>(`/conflicts/${conflict.id}/acknowledge`, {
        method: "POST",
        body: JSON.stringify({ rationale: rationale.trim() }),
      });
      onAcknowledgeSuccess(updated);
      onClose();
    } catch (err: unknown) {
      if (err instanceof ProblemDetailsError) {
        setErrorMsg(err.title || "Failed to acknowledge conflict.");
      } else {
        setErrorMsg("Failed to connect to conflict reconciliation service.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const getPriorityBadge = (priority: "high" | "moderate" | "low") => {
    if (priority === "high") {
      return (
        <Badge variant="destructive" className="flex items-center gap-1">
          <ShieldAlert className="h-3 w-3" /> High Review Priority
        </Badge>
      );
    }
    if (priority === "moderate") {
      return (
        <Badge className="bg-amber-100 text-amber-800 border-amber-300 flex items-center gap-1">
          <AlertTriangle className="h-3 w-3" /> Moderate Review Priority
        </Badge>
      );
    }
    return (
      <Badge variant="outline" className="flex items-center gap-1">
        <Info className="h-3 w-3" /> Low Review Priority
      </Badge>
    );
  };

  return (
    <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
      <DialogHeader>
        <div className="flex items-center justify-between gap-4 mb-2">
          {getPriorityBadge(conflict.review_priority)}
          <Badge variant="secondary" className="uppercase font-mono text-xs">
            {conflict.conflict_type.replace(/_/g, " ")}
          </Badge>
        </div>
        <DialogTitle className="text-xl leading-tight font-semibold text-slate-900">
          {conflict.title}
        </DialogTitle>
        <DialogDescription className="text-sm text-slate-500">
          Advisory Clinical Decision Support &bull; Encounter Cross-Reference
        </DialogDescription>
      </DialogHeader>

      <div className="space-y-4 my-2">
        {/* Clinical Pharmacology / Safety Summary */}
        {conflict.clinical_summary && (
          <div className="bg-slate-50 border border-slate-200 rounded-md p-3 text-sm text-slate-800 leading-relaxed">
            <span className="font-semibold text-slate-900 block mb-1">Clinical Evaluation Summary:</span>
            {conflict.clinical_summary}
          </div>
        )}

        {/* Side-by-Side Relational Sources */}
        {conflict.sources && conflict.sources.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
              Identified Discrepancy Citations ({conflict.sources.length})
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {conflict.sources.map((src, idx) => (
                <div
                  key={src.id || idx}
                  className="border border-slate-200 rounded-lg p-3 bg-white shadow-sm flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <FileText className="h-4 w-4 text-emerald-600 shrink-0" />
                      <span className="text-xs font-semibold text-slate-700 capitalize">
                        {src.role_in_conflict.replace(/_/g, " ")}
                      </span>
                    </div>
                    <p className="text-xs text-slate-800 bg-slate-50 p-2 rounded border border-slate-100 font-mono">
                      {src.citation_text}
                    </p>
                  </div>
                  {src.document_id && (
                    <div className="mt-2 text-[11px] text-slate-400">
                      Linked Document ID: {src.document_id.slice(0, 8)}...
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Mandatory Clinical Governance Disclaimer */}
        <Alert className="border-amber-200 bg-amber-50 text-amber-900">
          <Info className="h-4 w-4 text-amber-600" />
          <AlertTitle className="text-xs font-semibold">Advisory Decision Support Notice</AlertTitle>
          <AlertDescription className="text-xs leading-normal">
            Acknowledging this advisory alert records your documented clinical rationale and preserves auditability.
            <strong> It does NOT automatically discontinue medications or modify patient prescriptions.</strong> Any order
            adjustments must be placed through standard clinical order entry.
          </AlertDescription>
        </Alert>

        {/* Clinician Rationale Input or View */}
        {isAcknowledged ? (
          <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3">
            <div className="flex items-center gap-2 text-emerald-800 font-semibold text-xs mb-1">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              Acknowledged by Attending Clinician
            </div>
            <p className="text-xs text-emerald-900 italic">
              &ldquo;{conflict.clinician_rationale}&rdquo;
            </p>
            {conflict.acknowledged_at && (
              <div className="text-[11px] text-emerald-700 mt-1">
                Recorded at: {new Date(conflict.acknowledged_at).toLocaleString()}
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-700 block">
              Documented Clinical Review Rationale <span className="text-red-500">*</span>
            </label>
            <textarea
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              placeholder="Document clinical rationale (e.g., 'Patient tolerates cephalosporins well with mild childhood rash history only; benefit outweighs risk; monitored closely.')"
              rows={3}
              className="w-full text-xs p-2.5 rounded-md border border-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-500 text-slate-900"
            />
            <p className="text-[11px] text-slate-400">
              Minimum 10 characters required for clinical audit compliance.
            </p>
          </div>
        )}

        {errorMsg && (
          <Alert variant="destructive" className="py-2">
            <AlertDescription className="text-xs">{errorMsg}</AlertDescription>
          </Alert>
        )}
      </div>

      <DialogFooter className="gap-2 sm:gap-0">
        <Button variant="outline" onClick={onClose} disabled={submitting}>
          Close
        </Button>
        {!isAcknowledged && (
          <Button
            onClick={handleAcknowledge}
            disabled={submitting || rationale.trim().length < 10}
            className="bg-emerald-700 hover:bg-emerald-800 text-white"
          >
            {submitting ? "Recording Rationale..." : "Acknowledge & Record Rationale"}
          </Button>
        )}
      </DialogFooter>
    </DialogContent>
  );
}

export function ConflictReconciliationModal({
  conflict,
  open,
  onClose,
  onAcknowledgeSuccess,
}: ConflictReconciliationModalProps) {
  if (!conflict) return null;

  return (
    <Dialog open={open} onOpenChange={(val) => !val && onClose()}>
      <ConflictDialogBody
        key={conflict.id}
        conflict={conflict}
        onClose={onClose}
        onAcknowledgeSuccess={onAcknowledgeSuccess}
      />
    </Dialog>
  );
}

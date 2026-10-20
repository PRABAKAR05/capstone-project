"use client";

import React, { useEffect, useState, use } from "react";
import Link from "next/link";
import {
  FileText,
  CheckCircle,
  XCircle,
  Edit3,
  Download,
  ArrowLeft,
  AlertCircle,
  Activity,
  Pill,
  Stethoscope,
  FlaskConical,
  ShieldAlert,
  Save,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "@/lib/api";

interface ExtractedEntity {
  id: string;
  hospital_id: string;
  document_id: string;
  patient_id: string;
  entity_category: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  extracted_data: Record<string, any>;
  confidence_score: number | null;
  verification_status: "pending" | "verified" | "rejected" | "edited";
  verified_by: string | null;
  verified_at: string | null;
  doctor_notes: string | null;
}

interface ClinicalDocument {
  id: string;
  hospital_id: string;
  patient_id: string;
  document_type: string;
  file_name: string;
  mime_type: string;
  file_size_bytes: number;
  ocr_status: string;
  raw_text: string | null;
  created_at: string;
}

export default function DoctorDocumentReviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const resolvedParams = use(params);
  const docId = resolvedParams.id;

  const [document, setDocument] = useState<ClinicalDocument | null>(null);
  const [entities, setEntities] = useState<ExtractedEntity[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<string>("all");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editNotes, setEditNotes] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    async function fetchData() {
      try {
        setLoading(true);
        const [docData, entitiesData] = await Promise.all([
          apiFetch<ClinicalDocument>(`/documents/${docId}`),
          apiFetch<ExtractedEntity[]>(`/documents/${docId}/entities`),
        ]);

        if (!ignore) {
          setDocument(docData);
          setEntities(entitiesData);
        }
      } catch (err: unknown) {
        if (!ignore) {
          setError(err instanceof Error ? err.message : "Failed to load clinical document.");
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }
    fetchData();
    return () => {
      ignore = true;
    };
  }, [docId]);

  const handleVerifySingle = async (
    entityId: string,
    status: "verified" | "rejected" | "edited",
    notes?: string
  ) => {
    try {
      const payload = {
        entities: [
          {
            id: entityId,
            verification_status: status,
            doctor_notes: notes || editNotes || undefined,
          },
        ],
      };

      const updated = await apiFetch<ExtractedEntity[]>(`/documents/${docId}/verify`, {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setEntities(updated);
      setEditingId(null);
      setEditNotes("");
      setSuccessMsg(`Entity updated to ${status}.`);
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Verification request failed.");
    }
  };

  const handleVerifyAllPending = async () => {
    const pendingEntities = entities.filter((e) => e.verification_status === "pending");
    if (pendingEntities.length === 0) return;

    try {
      const payload = {
        entities: pendingEntities.map((e) => ({
          id: e.id,
          verification_status: "verified",
          doctor_notes: "Batch verified by attending physician.",
        })),
      };

      const updated = await apiFetch<ExtractedEntity[]>(`/documents/${docId}/verify`, {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setEntities(updated);
      setSuccessMsg(`Successfully verified ${pendingEntities.length} entities!`);
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Batch verification failed.");
    }
  };

  const filteredEntities = entities.filter((e) => {
    if (activeTab === "all") return true;
    return e.entity_category === activeTab;
  });

  const pendingCount = entities.filter((e) => e.verification_status === "pending").length;
  const verifiedCount = entities.filter((e) => e.verification_status === "verified").length;

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-48" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-[600px] w-full" />
          <Skeleton className="h-[600px] w-full" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back and Title Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link href="/doctor">
            <Button variant="outline" size="sm" className="h-9 w-9 p-0">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
              <FileText className="h-5 w-5 text-teal-600" />
              {document?.file_name || "Document Review"}
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Type: <span className="font-semibold capitalize">{document?.document_type.replace("_", " ")}</span> • 
              Uploaded: {document ? new Date(document.created_at).toLocaleString() : ""}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <a
            href={`/api/v1/documents/${docId}/download`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex"
          >
            <Button variant="outline" size="sm" className="gap-2">
              <Download className="h-4 w-4" />
              Download Original
            </Button>
          </a>
          <Button
            variant="primary"
            size="sm"
            onClick={handleVerifyAllPending}
            disabled={pendingCount === 0}
            className="gap-2"
          >
            <CheckCircle className="h-4 w-4" />
            Verify All ({pendingCount})
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive" className="flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </Alert>
      )}

      {successMsg && (
        <Alert variant="success" className="flex items-center gap-2">
          <CheckCircle className="h-4 w-4 shrink-0 text-emerald-600" />
          <span>{successMsg}</span>
        </Alert>
      )}

      {/* Side-by-Side Review Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        {/* Left Pane: Document Text Preview */}
        <Card className="flex flex-col h-[700px]">
          <CardHeader className="py-3 px-4 border-b border-slate-100 flex flex-row items-center justify-between">
            <CardTitle className="text-sm font-semibold text-slate-800 flex items-center gap-2">
              <FileText className="h-4 w-4 text-teal-600" />
              Extracted Document Text
            </CardTitle>
            <Badge variant={document?.ocr_status === "completed" ? "teal" : "warning"}>
              OCR: {document?.ocr_status}
            </Badge>
          </CardHeader>
          <CardContent className="flex-1 overflow-auto p-4 bg-slate-50 font-mono text-xs text-slate-800 leading-relaxed whitespace-pre-wrap select-text">
            {document?.raw_text || (
              <div className="h-full flex items-center justify-center text-slate-400">
                No text layer detected in document.
              </div>
            )}
          </CardContent>
        </Card>

        {/* Right Pane: Structured Extraction Review */}
        <Card className="flex flex-col h-[700px]">
          <CardHeader className="py-3 px-4 border-b border-slate-100 flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-semibold text-slate-800">
                Clinical Entities Verification
              </CardTitle>
              <div className="flex items-center gap-2 text-xs">
                <span className="text-emerald-700 font-semibold">{verifiedCount} Verified</span>
                <span className="text-slate-300">•</span>
                <span className="text-amber-700 font-semibold">{pendingCount} Pending</span>
              </div>
            </div>

            {/* Filter Tabs */}
            <div className="flex gap-1 overflow-x-auto pt-1">
              {[
                { id: "all", label: "All" },
                { id: "diagnosis", label: "Diagnoses" },
                { id: "medication", label: "Medications" },
                { id: "lab_result", label: "Labs" },
                { id: "vital_sign", label: "Vitals" },
                { id: "allergy", label: "Allergies" },
              ].map((t) => (
                <button
                  key={t.id}
                  onClick={() => setActiveTab(t.id)}
                  className={`px-2.5 py-1 text-xs rounded-md font-medium transition-colors ${
                    activeTab === t.id
                      ? "bg-teal-600 text-white"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </CardHeader>

          {/* Entity List */}
          <CardContent className="flex-1 overflow-auto p-4 space-y-3">
            {filteredEntities.length === 0 ? (
              <div className="h-full flex items-center justify-center text-sm text-slate-400">
                No entities found in this category.
              </div>
            ) : (
              filteredEntities.map((entity) => {
                const data = entity.extracted_data;
                const isEditing = editingId === entity.id;

                return (
                  <div
                    key={entity.id}
                    className={`rounded-lg border p-3 transition-shadow ${
                      entity.verification_status === "verified"
                        ? "border-emerald-200 bg-emerald-50/20"
                        : entity.verification_status === "rejected"
                        ? "border-rose-200 bg-rose-50/20 opacity-60"
                        : "border-slate-200 bg-white shadow-2xs"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        {entity.entity_category === "diagnosis" && (
                          <Stethoscope className="h-4 w-4 text-indigo-600" />
                        )}
                        {entity.entity_category === "medication" && (
                          <Pill className="h-4 w-4 text-emerald-600" />
                        )}
                        {entity.entity_category === "lab_result" && (
                          <FlaskConical className="h-4 w-4 text-amber-600" />
                        )}
                        {entity.entity_category === "vital_sign" && (
                          <Activity className="h-4 w-4 text-rose-600" />
                        )}
                        {entity.entity_category === "allergy" && (
                          <ShieldAlert className="h-4 w-4 text-red-600" />
                        )}

                        <span className="text-xs font-bold text-slate-900 capitalize">
                          {entity.entity_category.replace("_", " ")}
                        </span>

                        <Badge
                          variant={
                            entity.verification_status === "verified"
                              ? "teal"
                              : entity.verification_status === "rejected"
                              ? "destructive"
                              : "outline"
                          }
                          className="text-[10px] py-0 px-1.5"
                        >
                          {entity.verification_status}
                        </Badge>
                      </div>

                      {/* Action buttons */}
                      <div className="flex items-center gap-1">
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 px-2 text-xs text-emerald-700 hover:bg-emerald-50"
                          onClick={() => handleVerifySingle(entity.id, "verified")}
                          disabled={entity.verification_status === "verified"}
                        >
                          <CheckCircle className="h-3.5 w-3.5 mr-1" />
                          Verify
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 px-2 text-xs text-rose-700 hover:bg-rose-50"
                          onClick={() => handleVerifySingle(entity.id, "rejected")}
                          disabled={entity.verification_status === "rejected"}
                        >
                          <XCircle className="h-3.5 w-3.5 mr-1" />
                          Reject
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 px-2 text-xs text-slate-600"
                          onClick={() => {
                            setEditingId(isEditing ? null : entity.id);
                            setEditNotes(entity.doctor_notes || "");
                          }}
                        >
                          <Edit3 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>

                    {/* Extracted Details Render */}
                    <div className="mt-2 text-xs text-slate-700 space-y-1">
                      {entity.entity_category === "diagnosis" && (
                        <div>
                          <span className="font-semibold text-slate-900">{data.condition}</span>
                          {data.icd_code && (
                            <span className="ml-2 text-slate-500 font-mono">[{data.icd_code}]</span>
                          )}
                        </div>
                      )}

                      {entity.entity_category === "medication" && (
                        <div>
                          <span className="font-semibold text-slate-900">{data.drug_name}</span>
                          {data.dosage && <span className="ml-2 text-slate-600 font-medium">{data.dosage}</span>}
                          {data.frequency && <span className="ml-2 text-slate-500">• {data.frequency}</span>}
                        </div>
                      )}

                      {entity.entity_category === "lab_result" && (
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-900">{data.test_name}:</span>
                          <span className="font-bold text-slate-800">{data.value} {data.unit}</span>
                          {data.reference_range && (
                            <span className="text-slate-400">(Ref: {data.reference_range})</span>
                          )}
                          {data.abnormal_flag && (
                            <Badge variant="destructive" className="text-[10px] py-0 px-1">
                              Abnormal
                            </Badge>
                          )}
                        </div>
                      )}

                      {entity.entity_category === "vital_sign" && (
                        <div>
                          <span className="font-semibold text-slate-900">{data.vital_name}:</span>
                          <span className="ml-2 font-bold text-slate-800">{data.value} {data.unit}</span>
                        </div>
                      )}

                      {entity.entity_category === "allergy" && (
                        <div>
                          <span className="font-semibold text-slate-900">{data.allergen}</span>
                          {data.reaction && <span className="ml-2 text-slate-500">({data.reaction})</span>}
                        </div>
                      )}

                      {entity.doctor_notes && (
                        <p className="text-[11px] text-teal-800 bg-teal-50/50 p-1 rounded mt-1">
                          <strong>Note:</strong> {entity.doctor_notes}
                        </p>
                      )}
                    </div>

                    {/* Inline Edit Form */}
                    {isEditing && (
                      <div className="mt-2 pt-2 border-t border-slate-200 space-y-2">
                        <textarea
                          placeholder="Add clinical observation or correction notes..."
                          value={editNotes}
                          onChange={(e) => setEditNotes(e.target.value)}
                          className="w-full text-xs rounded border border-slate-300 p-2 focus:ring-1 focus:ring-teal-500"
                          rows={2}
                        />
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="primary"
                            size="sm"
                            className="h-7 text-xs gap-1"
                            onClick={() => handleVerifySingle(entity.id, "edited", editNotes)}
                          >
                            <Save className="h-3 w-3" />
                            Save Notes
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

"use client";

import React, { useEffect, useState } from "react";
import {
  FileText,
  UploadCloud,
  Download,
  CheckCircle2,
  Clock,
  AlertCircle,
  FileSearch,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { DocumentUploadModal } from "@/components/documents/document-upload-modal";
import { PatientSafetyAdvisory } from "@/components/conflicts/patient-safety-advisory";
import { useAuth } from "@/lib/auth-context";
import { apiFetch } from "@/lib/api";

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

export default function PatientDocumentsPage() {
  const { user } = useAuth();
  const [documents, setDocuments] = useState<ClinicalDocument[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [uploadModalOpen, setUploadModalOpen] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Default seed patient ID for demo if not set
  const patientId = user?.patient_id || "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa";

  const fetchDocuments = React.useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiFetch<ClinicalDocument[]>("/documents");
      setDocuments(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load clinical documents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let ignore = false;
    async function load() {
      try {
        setLoading(true);
        const data = await apiFetch<ClinicalDocument[]>("/documents");
        if (!ignore) setDocuments(data);
      } catch (err: unknown) {
        if (!ignore) setError(err instanceof Error ? err.message : "Failed to load clinical documents");
      } finally {
        if (!ignore) setLoading(false);
      }
    }
    load();
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <FileText className="h-6 w-6 text-teal-600" />
            My Clinical Documents
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            View discharge summaries, outside lab reports, prescriptions, and physician records.
          </p>
        </div>

        <Button
          variant="primary"
          onClick={() => setUploadModalOpen(true)}
          className="gap-2 shrink-0"
        >
          <UploadCloud className="h-4 w-4" />
          Upload New Document
        </Button>
      </div>

      {error && (
        <Alert variant="destructive" className="flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </Alert>
      )}

      {/* Phase 7 Patient Safety Advisory */}
      <PatientSafetyAdvisory />

      {/* Zero-PHI Privacy Notice */}
      <div className="rounded-lg border border-teal-200 bg-teal-50/50 p-3 text-xs text-teal-900 flex items-start gap-2">
        <Badge variant="teal" className="shrink-0 text-[10px] py-0 px-1.5">
          Verified Clinical Storage
        </Badge>
        <span>
          Uploaded documents are analyzed using private OCR and structured extraction. All medical findings remain in a <strong>pending review</strong> state until signed off by your attending doctor.
        </span>
      </div>

      {/* Document Timeline Cards */}
      {loading ? (
        <div className="space-y-3">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : documents.length === 0 ? (
        <Card className="text-center py-12">
          <CardContent className="space-y-3">
            <FileSearch className="h-12 w-12 text-slate-300 mx-auto" />
            <p className="text-sm font-semibold text-slate-700">No clinical documents uploaded yet.</p>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              Upload past hospital discharge summaries, external lab tests, or prescriptions so your care team has full context.
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setUploadModalOpen(true)}
              className="mt-2"
            >
              Upload Your First Document
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {documents.map((doc) => (
            <Card key={doc.id} className="hover:shadow-md transition-shadow flex flex-col justify-between">
              <CardHeader className="p-4 pb-2">
                <div className="flex items-start justify-between gap-2">
                  <Badge variant="teal" className="capitalize text-[10px]">
                    {doc.document_type.replace("_", " ")}
                  </Badge>
                  <span className="text-[11px] text-slate-400">
                    {new Date(doc.created_at).toLocaleDateString()}
                  </span>
                </div>
                <CardTitle className="text-sm font-bold text-slate-800 truncate mt-2" title={doc.file_name}>
                  {doc.file_name}
                </CardTitle>
              </CardHeader>

              <CardContent className="p-4 pt-0 space-y-3">
                <div className="flex items-center justify-between text-xs text-slate-500">
                  <span>{(doc.file_size_bytes / 1024).toFixed(0)} KB</span>
                  <span className="flex items-center gap-1 font-medium">
                    {doc.ocr_status === "completed" ? (
                      <>
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                        <span className="text-emerald-700">Processed</span>
                      </>
                    ) : (
                      <>
                        <Clock className="h-3.5 w-3.5 text-amber-500" />
                        <span className="text-amber-700">{doc.ocr_status}</span>
                      </>
                    )}
                  </span>
                </div>

                <div className="pt-2 border-t border-slate-100 flex justify-end">
                  <a
                    href={`/api/v1/documents/${doc.id}/download`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <Button variant="outline" size="sm" className="h-8 text-xs gap-1.5">
                      <Download className="h-3.5 w-3.5" />
                      Download
                    </Button>
                  </a>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Upload Modal */}
      <DocumentUploadModal
        open={uploadModalOpen}
        onOpenChange={setUploadModalOpen}
        patientId={patientId}
        onUploadSuccess={() => fetchDocuments()}
      />
    </div>
  );
}

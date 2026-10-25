"use client";

import React, { useState, useRef } from "react";
import { UploadCloud, FileText, CheckCircle2, AlertCircle, X } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { getAuthToken, API_BASE_URL } from "@/lib/api";

interface DocumentUploadModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  patientId: string;
  onUploadSuccess?: (newDoc: unknown) => void;
}

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10MB

export function DocumentUploadModal({
  open,
  onOpenChange,
  patientId,
  onUploadSuccess,
}: DocumentUploadModalProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [docType, setDocType] = useState<string>("discharge_summary");
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<boolean>(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      if (selected.size > MAX_FILE_SIZE_BYTES) {
        setError("File exceeds the 10 MB maximum limit.");
        return;
      }
      const allowedExts = [".pdf", ".png", ".jpg", ".jpeg"];
      const ext = selected.name.substring(selected.name.lastIndexOf(".")).toLowerCase();
      if (!allowedExts.includes(ext)) {
        setError("Only PDF, PNG, and JPEG files are supported.");
        return;
      }
      setFile(selected);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setError(null);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const selected = e.dataTransfer.files[0];
      if (selected.size > MAX_FILE_SIZE_BYTES) {
        setError("File exceeds the 10 MB maximum limit.");
        return;
      }
      setFile(selected);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError("Please select a clinical document to upload.");
      return;
    }

    setIsUploading(true);
    setError(null);

    try {
      const token = await getAuthToken();
      const formData = new FormData();
      formData.append("patient_id", patientId);
      formData.append("document_type", docType);
      formData.append("file", file);

      const headers: Record<string, string> = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch(`${API_BASE_URL}/api/v1/documents/upload`, {
        method: "POST",
        headers,
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Upload failed with status ${res.status}`);
      }

      const doc = await res.json();
      setSuccess(true);
      if (onUploadSuccess) {
        onUploadSuccess(doc);
      }
      setTimeout(() => {
        setSuccess(false);
        setFile(null);
        onOpenChange(false);
      }, 1200);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to upload and process clinical document.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent onClose={() => onOpenChange(false)}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <UploadCloud className="h-5 w-5 text-teal-600" />
            Upload Clinical Document
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 pt-2">
          {error && (
            <Alert variant="destructive" className="py-2 text-sm flex items-start gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </Alert>
          )}

          {success && (
            <Alert variant="success" className="py-2 text-sm flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
              <span>Document uploaded and queued for clinical intelligence parsing!</span>
            </Alert>
          )}

          {isUploading && (
            <div className="rounded-lg bg-blue-50/80 border border-blue-200 p-3 text-xs text-blue-900 space-y-1.5 animate-pulse">
              <div className="flex items-center gap-2 font-bold text-blue-800">
                <span className="inline-block h-2 w-2 rounded-full bg-blue-600 animate-ping" />
                OCR & Clinical Entity Extraction in Progress
              </div>
              <p className="text-[11px] text-blue-700">
                Parsing clinical terms, dosages, lab values, and diagnoses. This typically takes 10–15 seconds. Please do not close this window.
              </p>
            </div>
          )}

          {/* Classification Selection */}
          <Select
            label="Document Classification"
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
          >
            <option value="discharge_summary">Discharge Summary</option>
            <option value="lab_report">Laboratory Report</option>
            <option value="prescription">Outside Prescription</option>
            <option value="referral">Referral / Consultation Note</option>
            <option value="other">Other Clinical Record</option>
          </Select>

          {/* Dropzone Area */}
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 p-6 text-center transition-colors hover:border-teal-500 hover:bg-teal-50/20 cursor-pointer"
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg"
              className="hidden"
              onChange={handleFileChange}
            />
            <UploadCloud className="h-10 w-10 text-slate-400 mb-2" />
            <p className="text-sm font-medium text-slate-700">
              Drag and drop your file here, or{" "}
              <span className="text-teal-600 underline">browse</span>
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Supports PDF, PNG, and JPEG up to 10 MB
            </p>
          </div>

          {/* Selected File Card */}
          {file && (
            <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-white p-3 shadow-2xs">
              <div className="flex items-center gap-3 truncate">
                <FileText className="h-6 w-6 text-teal-600 shrink-0" />
                <div className="truncate">
                  <p className="text-xs font-semibold text-slate-800 truncate">{file.name}</p>
                  <p className="text-[11px] text-slate-500">
                    {(file.size / (1024 * 1024)).toFixed(2)} MB • {file.type || "Document"}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setFile(null);
                }}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          )}

          {/* Privacy & Guardrail Notice */}
          <div className="rounded-lg bg-teal-50/50 p-2.5 text-xs text-teal-900 border border-teal-100 flex items-start gap-2">
            <Badge variant="teal" className="shrink-0 text-[10px] py-0 px-1.5">Zero-PHI</Badge>
            <span>
              All extractions default to <strong>Pending Clinician Review</strong>. Medical data is never merged without attending physician verification.
            </span>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
            <Button
              variant="outline"
              type="button"
              onClick={() => onOpenChange(false)}
              disabled={isUploading}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              type="button"
              onClick={handleUpload}
              isLoading={isUploading}
              disabled={!file || isUploading}
            >
              {isUploading ? "Extracting Entities..." : "Upload & Ingest"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

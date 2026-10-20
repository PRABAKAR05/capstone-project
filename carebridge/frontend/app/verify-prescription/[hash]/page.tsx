"use client";

import * as React from "react";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ShieldCheck, ShieldAlert, CheckCircle2, Clock, Building2, User, KeyRound } from "lucide-react";

interface VerificationResult {
  is_valid: boolean;
  status: string;
  prescription_id?: string;
  hospital_id?: string;
  hospital_name?: string;
  doctor_id?: string;
  issued_at?: string;
  valid_until?: string;
  items_count?: number;
  items_hash?: string;
  verification_hash?: string;
  message?: string;
}

function VerifyContent({ params }: { params: Promise<{ hash: string }> }) {
  const resolvedParams = React.use(params);
  const rawHash = resolvedParams?.hash as string;
  const verificationHash = rawHash ? decodeURIComponent(rawHash) : "";

  const [result, setResult] = React.useState<VerificationResult | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    if (!verificationHash) return;
    let ignore = false;

    async function verify() {
      setLoading(true);
      try {
        const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        const res = await fetch(`${backendUrl}/api/v1/prescriptions/verify/${encodeURIComponent(verificationHash)}`);
        const data = await res.json();
        if (!ignore) {
          setResult(data);
        }
      } catch {
        if (!ignore) {
          setResult({
            is_valid: false,
            status: "error",
            message: "Unable to contact verification service.",
          });
        }
      } finally {
        if (!ignore) setLoading(false);
      }
    }

    verify();
    return () => {
      ignore = true;
    };
  }, [verificationHash]);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4">
      <Card className="max-w-md w-full shadow-lg border-indigo-100">
        <CardHeader className="text-center pb-4 border-b bg-gradient-to-b from-indigo-50/50 to-white">
          <div className="mx-auto w-12 h-12 rounded-full bg-indigo-100 flex items-center justify-center mb-2">
            <ShieldCheck className="w-6 h-6 text-indigo-600" />
          </div>
          <CardTitle className="text-lg font-bold text-indigo-950">
            CareBridge Digital Prescription Verification
          </CardTitle>
          <CardDescription className="text-xs">
            Public Authenticity & Tamper-Detection Engine
          </CardDescription>
        </CardHeader>

        <CardContent className="pt-6 space-y-4 text-xs">
          {loading ? (
            <div className="py-8 text-center text-muted-foreground">
              Verifying cryptographic digital signature...
            </div>
          ) : result ? (
            <div className="space-y-4">
              {/* Status Badge */}
              <div className="text-center">
                {result.is_valid ? (
                  <div className="space-y-1">
                    <Badge variant="outline" className="bg-emerald-100 text-emerald-800 border-emerald-300 text-sm py-1 px-3 gap-1.5">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" /> Cryptographically Verified
                    </Badge>
                    <p className="text-[11px] text-muted-foreground mt-1">
                      {result.status === "expired" ? "This prescription is authentic but has expired." : "This prescription signature is authentic and unaltered."}
                    </p>
                  </div>
                ) : (
                  <div className="space-y-1">
                    <Badge variant="outline" className="bg-red-100 text-red-800 border-red-300 text-sm py-1 px-3 gap-1.5">
                      <ShieldAlert className="w-4 h-4 text-red-600" /> Signature Unverified / Tampered
                    </Badge>
                    <p className="text-[11px] text-red-600 mt-1">
                      {result.message || "Invalid signature format or mismatched payload."}
                    </p>
                  </div>
                )}
              </div>

              {result.is_valid && (
                <div className="p-3 bg-muted/30 rounded-lg space-y-2 border">
                  <div className="flex items-center justify-between pb-1.5 border-b">
                    <span className="flex items-center gap-1.5 font-semibold text-muted-foreground">
                      <Building2 className="w-3.5 h-3.5" /> Issuing Healthcare Provider
                    </span>
                    <span className="font-semibold text-foreground">{result.hospital_name}</span>
                  </div>

                  <div className="flex items-center justify-between pb-1.5 border-b">
                    <span className="flex items-center gap-1.5 font-semibold text-muted-foreground">
                      <User className="w-3.5 h-3.5" /> Issuing Physician ID
                    </span>
                    <span className="font-mono text-[10px] text-foreground">{result.doctor_id}</span>
                  </div>

                  <div className="flex items-center justify-between pb-1.5 border-b">
                    <span className="flex items-center gap-1.5 font-semibold text-muted-foreground">
                      <Clock className="w-3.5 h-3.5" /> Issued Timestamp
                    </span>
                    <span>{result.issued_at ? new Date(result.issued_at).toLocaleString() : "—"}</span>
                  </div>

                  <div className="flex items-center justify-between pb-1.5 border-b">
                    <span className="font-semibold text-muted-foreground">Valid Until</span>
                    <span>{result.valid_until ? new Date(result.valid_until).toLocaleDateString() : "—"}</span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-muted-foreground">Medications Count</span>
                    <span className="font-semibold text-indigo-700">{result.items_count} item(s)</span>
                  </div>
                </div>
              )}

              {/* Cryptographic hash details */}
              <div className="space-y-1 bg-slate-100 p-2.5 rounded border text-[10px] font-mono text-muted-foreground break-all">
                <div className="flex items-center gap-1 text-slate-700 font-semibold mb-0.5">
                  <KeyRound className="w-3 h-3 text-indigo-600" /> Signature Hash
                </div>
                <div>{verificationHash}</div>
              </div>

              {/* Zero-PII disclosure note */}
              <p className="text-[10px] text-center text-muted-foreground italic">
                Zero-PHI Architecture: In compliance with HIPAA and national privacy frameworks, patient names and clinical notes are never exposed on public verification channels.
              </p>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

export default function VerifyPrescriptionPage({
  params,
}: {
  params: Promise<{ hash: string }>;
}) {
  return (
    <React.Suspense
      fallback={
        <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4 text-xs text-muted-foreground">
          Loading verification record...
        </div>
      }
    >
      <VerifyContent params={params} />
    </React.Suspense>
  );
}

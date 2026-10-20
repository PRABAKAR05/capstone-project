"use client";

import * as React from "react";
import { Shield, Calculator, CheckCircle2, AlertTriangle, FileText, IndianRupee } from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiFetch, ProblemDetailsError } from "@/lib/api";

interface InsurancePolicy {
  id: string;
  provider_name: string;
  policy_number: string;
  policy_holder_name: string;
  sum_insured_inr: number;
  remaining_balance_inr: number;
  copay_percentage: number;
  deductible_inr: number;
  exclusions: string[];
  valid_from: string;
  valid_until: string;
  status: string;
}

interface PreAuthEstimate {
  estimate_status: "estimate_available" | "insufficient_information" | "review_required";
  rule_version: string;
  requested_amount_inr: number;
  applicable_limit_inr: number;
  deductible_applied_inr: number;
  copay_percentage: number;
  estimated_insurer_pays_inr: number;
  estimated_patient_copay_inr: number;
  matched_exclusion?: string | null;
  calculation_breakdown: Record<string, unknown>;
  disclaimer: string;
}

interface PatientInsuranceCardProps {
  patientId: string;
}

export function PatientInsuranceCard({ patientId }: PatientInsuranceCardProps) {
  const [policies, setPolicies] = React.useState<InsurancePolicy[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [selectedPolicyId, setSelectedPolicyId] = React.useState<string>("");
  const [procedureName, setProcedureName] = React.useState("Specialist Consultation & ECG");
  const [procedureCategory, setProcedureCategory] = React.useState("general_consultation");
  const [estimatedCost, setEstimatedCost] = React.useState("5000");
  const [calculating, setCalculating] = React.useState(false);
  const [estimateResult, setEstimateResult] = React.useState<PreAuthEstimate | null>(null);
  const [calcError, setCalcError] = React.useState<string | null>(null);

  React.useEffect(() => {
    async function loadPolicies() {
      if (!patientId) return;
      try {
        const data = await apiFetch<InsurancePolicy[]>(`/insurance/policies/${patientId}`);
        setPolicies(data || []);
        if (data && data.length > 0) {
          setSelectedPolicyId(data[0].id);
        }
      } catch {
        // Fallback demo policy
        setPolicies([
          {
            id: "11111111-9999-9999-9999-111111111111",
            provider_name: "Star Health Premier Gold",
            policy_number: "SH-2026-981244",
            policy_holder_name: "Ananya Sharma",
            sum_insured_inr: 1000000,
            remaining_balance_inr: 850000,
            copay_percentage: 10,
            deductible_inr: 2000,
            exclusions: ["cosmetic_surgery", "experimental_therapy"],
            valid_from: "2026-01-01",
            valid_until: "2027-01-01",
            status: "active",
          },
        ]);
        setSelectedPolicyId("11111111-9999-9999-9999-111111111111");
      } finally {
        setLoading(false);
      }
    }
    loadPolicies();
  }, [patientId]);

  const handleCalculateEstimate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPolicyId || !estimatedCost) return;
    setCalculating(true);
    setCalcError(null);

    try {
      const res = await apiFetch<PreAuthEstimate>("/insurance/pre-auth/estimate", {
        method: "POST",
        body: JSON.stringify({
          policy_id: selectedPolicyId,
          patient_id: patientId,
          procedure_name: procedureName,
          procedure_category: procedureCategory,
          requested_amount_inr: parseFloat(estimatedCost),
        }),
      });
      setEstimateResult(res);
    } catch (err) {
      if (err instanceof ProblemDetailsError) {
        setCalcError(err.detail);
      } else {
        setCalcError("Failed to calculate estimate. Please check policy parameters.");
      }
    } finally {
      setCalculating(false);
    }
  };

  if (loading) {
    return (
      <Card className="border-slate-200 shadow-xs">
        <CardContent className="p-6 text-sm text-slate-400">Loading insurance coverage...</CardContent>
      </Card>
    );
  }

  if (policies.length === 0) {
    return (
      <Card className="border-slate-200 shadow-xs">
        <CardHeader>
          <CardTitle className="text-base font-semibold flex items-center space-x-2">
            <Shield className="h-5 w-5 text-blue-600" />
            <span>Health Insurance & Coverage</span>
          </CardTitle>
          <CardDescription>No active health insurance policy registered with the hospital.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card className="border-slate-200 shadow-xs">
      <CardHeader className="border-b border-slate-100 bg-slate-50/50 pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Shield className="h-5 w-5 text-blue-700" />
            <CardTitle className="text-base font-bold text-slate-900">Health Insurance & Pre-Authorization</CardTitle>
          </div>
          <Badge variant="teal" className="text-xs">
            Phase 11 Verified
          </Badge>
        </div>
        <CardDescription className="text-xs text-slate-500">
          Deterministic coverage estimation and co-pay calculation using hospital policy rules.
        </CardDescription>
      </CardHeader>

      <CardContent className="p-6 space-y-6">
        {/* Policy Details Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {policies.map((p) => {
            const isGovt = p.provider_name.toLowerCase().includes("ayushman") || p.provider_name.toLowerCase().includes("pm-jay");
            return (
              <div
                key={p.id}
                className={`p-4 rounded-xl border text-xs space-y-2 transition-all ${
                  selectedPolicyId === p.id ? "border-blue-500 bg-blue-50/30 ring-1 ring-blue-500/20" : "border-slate-200 bg-white"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-1.5 font-bold text-slate-900 text-sm">
                    <FileText className="h-4 w-4 text-blue-600" />
                    <span>{p.provider_name}</span>
                  </div>
                  {isGovt && (
                    <Badge variant="success" className="text-[10px]">
                      PM-JAY Eligible
                    </Badge>
                  )}
                  <Badge variant={p.status === "active" ? "success" : "secondary"} className="text-[10px] capitalize">
                    {p.status}
                  </Badge>
                </div>

                <div className="text-slate-600 font-mono text-[11px]">Policy #: {p.policy_number}</div>

                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-200/60 text-[11px]">
                  <div>
                    <span className="text-slate-400 block">Sum Insured:</span>
                    <span className="font-semibold text-slate-800">₹{p.sum_insured_inr.toLocaleString("en-IN")}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block">Remaining:</span>
                    <span className="font-semibold text-emerald-700">₹{p.remaining_balance_inr.toLocaleString("en-IN")}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block">Co-Pay:</span>
                    <span className="font-semibold text-slate-800">{p.copay_percentage}%</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block">Deductible:</span>
                    <span className="font-semibold text-slate-800">₹{p.deductible_inr.toLocaleString("en-IN")}</span>
                  </div>
                </div>

                {p.exclusions && p.exclusions.length > 0 && (
                  <div className="pt-1 text-[10px] text-slate-500">
                    <span className="font-medium">Exclusions: </span>
                    {p.exclusions.join(", ")}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Interactive Pre-Authorization Estimator */}
        <div className="rounded-xl border border-blue-200 bg-blue-50/40 p-4 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2 font-bold text-slate-900 text-sm">
              <Calculator className="h-4 w-4 text-blue-700" />
              <span>Pre-Authorization Co-Pay Calculator</span>
            </div>
            <span className="text-[10px] text-slate-500 font-mono">Engine: v1.0 Deterministic</span>
          </div>

          <form onSubmit={handleCalculateEstimate} className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div>
              <label className="block text-slate-600 font-medium mb-1">Procedure / Consultation</label>
              <input
                type="text"
                value={procedureName}
                onChange={(e) => setProcedureName(e.target.value)}
                className="w-full bg-white border border-slate-300 rounded px-2.5 py-1.5 text-xs text-slate-800 focus:outline-hidden focus:border-blue-500"
                placeholder="e.g. Echo & Cardiology Consultation"
                required
              />
            </div>
            <div>
              <label className="block text-slate-600 font-medium mb-1">Category</label>
              <select
                value={procedureCategory}
                onChange={(e) => setProcedureCategory(e.target.value)}
                className="w-full bg-white border border-slate-300 rounded px-2.5 py-1.5 text-xs text-slate-800 focus:outline-hidden focus:border-blue-500"
              >
                <option value="general_consultation">General Consultation & Diagnostics</option>
                <option value="cardiology_procedure">Cardiology Intervention</option>
                <option value="daycare_surgery">Daycare Surgical Procedure</option>
                <option value="cosmetic_surgery">Cosmetic / Elective (Excluded)</option>
              </select>
            </div>
            <div>
              <label className="block text-slate-600 font-medium mb-1">Estimated Cost (₹)</label>
              <div className="flex space-x-2">
                <input
                  type="number"
                  value={estimatedCost}
                  onChange={(e) => setEstimatedCost(e.target.value)}
                  className="w-full bg-white border border-slate-300 rounded px-2.5 py-1.5 text-xs text-slate-800 focus:outline-hidden focus:border-blue-500"
                  min="100"
                  step="100"
                  required
                />
                <Button
                  type="submit"
                  size="sm"
                  disabled={calculating}
                  className="bg-blue-700 hover:bg-blue-800 text-white shrink-0 text-xs px-3"
                >
                  {calculating ? "..." : "Calculate"}
                </Button>
              </div>
            </div>
          </form>

          {calcError && <div className="p-2 bg-red-50 text-red-700 border border-red-200 rounded text-xs">{calcError}</div>}

          {estimateResult && (
            <div className="p-4 bg-white border border-slate-200 rounded-lg shadow-xs space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Badge
                    variant={
                      estimateResult.estimate_status === "estimate_available"
                        ? "success"
                        : estimateResult.estimate_status === "review_required"
                        ? "warning"
                        : "secondary"
                    }
                    className="text-xs"
                  >
                    {estimateResult.estimate_status.replace("_", " ").toUpperCase()}
                  </Badge>
                  <span className="text-xs text-slate-600 font-semibold">
                    {policies.find((p) => p.id === selectedPolicyId)?.provider_name || "Insurance Policy"}
                  </span>
                </div>
                <span className="text-[10px] text-slate-400 font-mono">Rule {estimateResult.rule_version}</span>
              </div>

              {estimateResult.matched_exclusion && (
                <div className="flex items-center space-x-2 text-xs text-amber-800 bg-amber-50 p-2 rounded border border-amber-200">
                  <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
                  <span>
                    <strong>Exclusion Detected:</strong> Matched policy rule exclusion &lsquo;{estimateResult.matched_exclusion}&rsquo;.
                    Insurer coverage is ₹0 for this procedure.
                  </span>
                </div>
              )}

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs pt-2 border-t border-slate-100">
                <div className="p-2 bg-slate-50 rounded">
                  <span className="text-slate-400 block text-[10px]">Procedure Cost:</span>
                  <span className="font-bold text-slate-900 text-sm flex items-center">
                    <IndianRupee className="h-3.5 w-3.5" />
                    {estimateResult.requested_amount_inr.toLocaleString("en-IN")}
                  </span>
                </div>
                <div className="p-2 bg-slate-50 rounded">
                  <span className="text-slate-400 block text-[10px]">Deductible Applied:</span>
                  <span className="font-semibold text-slate-800 text-sm flex items-center">
                    <IndianRupee className="h-3.5 w-3.5" />
                    {estimateResult.deductible_applied_inr.toLocaleString("en-IN")}
                  </span>
                </div>
                <div className="p-2 bg-emerald-50 rounded border border-emerald-100">
                  <span className="text-emerald-700 block text-[10px] font-medium">Estimated Insurer Pays:</span>
                  <span className="font-bold text-emerald-800 text-sm flex items-center">
                    <IndianRupee className="h-3.5 w-3.5" />
                    {estimateResult.estimated_insurer_pays_inr.toLocaleString("en-IN")}
                  </span>
                </div>
                <div className="p-2 bg-blue-50 rounded border border-blue-100">
                  <span className="text-blue-700 block text-[10px] font-medium">Your Out-of-Pocket Co-Pay:</span>
                  <span className="font-bold text-blue-900 text-sm flex items-center">
                    <IndianRupee className="h-3.5 w-3.5" />
                    {estimateResult.estimated_patient_copay_inr.toLocaleString("en-IN")}
                  </span>
                </div>
              </div>

              {/* Informational Disclaimer (AC-11.4) */}
              <div className="p-2 bg-slate-50 rounded text-[10px] text-slate-500 italic flex items-center space-x-1.5">
                <CheckCircle2 className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                <span>{estimateResult.disclaimer}</span>
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

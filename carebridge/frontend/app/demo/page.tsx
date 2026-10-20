"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogDescription, 
  DialogFooter 
} from "@/components/ui/dialog";
import { 
  Activity, 
  ShieldCheck, 
  FileText, 
  AlertTriangle, 
  ArrowLeft, 
  Lock, 
  Stethoscope, 
  Users, 
  Clock, 
  CheckCircle,
  ExternalLink,
  ClipboardList,
  FlaskConical
} from "lucide-react";

export default function GuidedDemoPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = React.useState<"doctor" | "nurse" | "lab_technician" | "patient" | "admin">("doctor");
  const [interceptModalOpen, setInterceptModalOpen] = React.useState(false);
  const [targetAction, setTargetAction] = React.useState<{ title: string; returnUrl: string }>({
    title: "Clinical Workstation",
    returnUrl: "/doctor"
  });

  const handleProtectedAction = (title: string, returnUrl: string) => {
    setTargetAction({ title, returnUrl });
    setInterceptModalOpen(true);
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans">
      {/* Top Demo Header */}
      <header className="border-b border-slate-200 bg-white sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2 text-slate-600 hover:text-slate-900 text-sm font-medium">
              <ArrowLeft className="h-4 w-4" />
              <span>Back to Home</span>
            </Link>
            <span className="text-slate-300">|</span>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-base text-slate-900">CareBridge AI</span>
              <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200 text-[10px] font-bold">
                GUIDED DEMO MODE
              </Badge>
            </div>
          </div>

          <Link href="/login">
            <Button size="sm" className="bg-blue-700 hover:bg-blue-800 text-white font-semibold">
              Sign In to Workstation
            </Button>
          </Link>
        </div>
      </header>

      {/* Main Showcase Container */}
      <main className="max-w-7xl mx-auto px-4 py-8 flex-1 w-full space-y-6">
        {/* Synthetic Disclaimer Banner */}
        <div className="p-3.5 rounded-xl border border-blue-200 bg-blue-50/80 flex items-center justify-between text-xs text-blue-900">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-blue-700 shrink-0" />
            <span>
              <strong>Simulated Evaluation Mode:</strong> Exploring pre-computed synthetic clinical telemetry. Real-time operations require authenticated session.
            </span>
          </div>
          <Badge className="bg-blue-700 text-white text-[10px]">Synthetic Data</Badge>
        </div>

        {/* Role Workspace Selector Tabs */}
        <div className="flex border-b border-slate-200 space-x-2 overflow-x-auto">
          <button
            onClick={() => setActiveTab("doctor")}
            className={`pb-3 px-4 text-sm font-semibold border-b-2 flex items-center gap-2 transition-all cursor-pointer whitespace-nowrap ${
              activeTab === "doctor"
                ? "border-blue-700 text-blue-700"
                : "border-transparent text-slate-600 hover:text-slate-900"
            }`}
          >
            <Stethoscope className="h-4 w-4" />
            <span>Doctor Workstation & IoMT</span>
          </button>
          <button
            onClick={() => setActiveTab("nurse")}
            className={`pb-3 px-4 text-sm font-semibold border-b-2 flex items-center gap-2 transition-all cursor-pointer whitespace-nowrap ${
              activeTab === "nurse"
                ? "border-blue-700 text-blue-700"
                : "border-transparent text-slate-600 hover:text-slate-900"
            }`}
          >
            <ClipboardList className="h-4 w-4" />
            <span>Nurse Workstation & Desk</span>
          </button>
          <button
            onClick={() => setActiveTab("lab_technician")}
            className={`pb-3 px-4 text-sm font-semibold border-b-2 flex items-center gap-2 transition-all cursor-pointer whitespace-nowrap ${
              activeTab === "lab_technician"
                ? "border-blue-700 text-blue-700"
                : "border-transparent text-slate-600 hover:text-slate-900"
            }`}
          >
            <FlaskConical className="h-4 w-4" />
            <span>Diagnostic Laboratory</span>
          </button>
          <button
            onClick={() => setActiveTab("patient")}
            className={`pb-3 px-4 text-sm font-semibold border-b-2 flex items-center gap-2 transition-all cursor-pointer whitespace-nowrap ${
              activeTab === "patient"
                ? "border-blue-700 text-blue-700"
                : "border-transparent text-slate-600 hover:text-slate-900"
            }`}
          >
            <Users className="h-4 w-4" />
            <span>Patient Self-Service Portal</span>
          </button>
          <button
            onClick={() => setActiveTab("admin")}
            className={`pb-3 px-4 text-sm font-semibold border-b-2 flex items-center gap-2 transition-all cursor-pointer whitespace-nowrap ${
              activeTab === "admin"
                ? "border-blue-700 text-blue-700"
                : "border-transparent text-slate-600 hover:text-slate-900"
            }`}
          >
            <Activity className="h-4 w-4" />
            <span>Hospital Administration</span>
          </button>
        </div>

        {/* Tab 1: Doctor Workstation Preview */}
        {activeTab === "doctor" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* CSCM-IoMT Telemetry Card */}
              <Card className="lg:col-span-2 border-slate-200 shadow-xs">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base flex items-center gap-2">
                      <Activity className="h-4 w-4 text-blue-700" />
                      <span>CSCM-IoMT Real-Time Telemetry Monitor</span>
                    </CardTitle>
                    <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200 text-xs">
                      Baseline Guard Active
                    </Badge>
                  </div>
                  <CardDescription className="text-xs">
                    Cross-sensor consistency verification over ICU telemetry (PPG, ECG, SpO2)
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="p-4 rounded-lg bg-slate-900 text-slate-100 font-mono text-xs space-y-2">
                    <div className="flex justify-between border-b border-slate-800 pb-2">
                      <span className="text-slate-400">IoMT Bedside Monitor:</span>
                      <span className="text-emerald-400 font-bold">DEVICE_ICU_BED_04</span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 py-1 text-center">
                      <div className="bg-slate-800 p-2 rounded">
                        <div className="text-[10px] text-slate-400">Heart Rate</div>
                        <div className="text-base font-bold text-white">74 BPM</div>
                      </div>
                      <div className="bg-slate-800 p-2 rounded">
                        <div className="text-[10px] text-slate-400">SpO2 Level</div>
                        <div className="text-base font-bold text-white">98%</div>
                      </div>
                      <div className="bg-slate-800 p-2 rounded">
                        <div className="text-[10px] text-slate-400">CSCM Inconsistency</div>
                        <div className="text-base font-bold text-emerald-400">0.03 (Normal)</div>
                      </div>
                    </div>
                    <p className="text-[11px] text-slate-400 pt-1">
                      Status: No cross-sensor anomaly detected. Deep learning temporal correlation confirmed.
                    </p>
                  </div>

                  <div className="flex justify-between items-center pt-2">
                    <span className="text-xs text-slate-500">Demonstration action:</span>
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => handleProtectedAction("Doctor Workstation", "/doctor")}
                      className="border-blue-300 text-blue-700 text-xs"
                    >
                      Open Live Physician Dashboard
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* Clinical Conflict Summary */}
              <Card className="border-slate-200 shadow-xs">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 text-amber-600" />
                    <span>Clinical Conflict Engine</span>
                  </CardTitle>
                  <CardDescription className="text-xs">
                    Autonomous safety review of newly extracted lab entities
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="p-3 rounded-lg border border-amber-200 bg-amber-50/60 text-xs text-amber-900 space-y-1">
                    <div className="font-bold flex items-center justify-between">
                      <span>Conflict: Drug-Drug Interaction</span>
                      <Badge className="bg-amber-600 text-white text-[9px]">High Priority</Badge>
                    </div>
                    <p className="text-[11px] text-amber-800/90">
                      Co-administration of Amlodipine 5mg and Simvastatin 40mg exceeds recommended AUC threshold.
                    </p>
                  </div>
                  <Button 
                    size="sm" 
                    onClick={() => handleProtectedAction("Clinical Conflict Review", "/doctor")}
                    className="w-full bg-slate-800 hover:bg-slate-900 text-white text-xs"
                  >
                    Review & Acknowledge Conflict
                  </Button>
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {/* Tab 2: Patient Portal Preview */}
        {/* Tab: Nurse Desk Preview */}
        {activeTab === "nurse" && (
          <Card className="border-slate-200 shadow-xs">
            <CardHeader>
              <CardTitle className="text-base">Clinical Nursing Desk & Rapid Check-In</CardTitle>
              <CardDescription className="text-xs">
                Patient check-in, token assignment, vitals prep, and care coordination task execution
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="bg-slate-100 text-slate-700">
                    <tr>
                      <th className="p-2.5">Token</th>
                      <th className="p-2.5">Patient Name</th>
                      <th className="p-2.5">Department</th>
                      <th className="p-2.5">Status</th>
                      <th className="p-2.5">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    <tr>
                      <td className="p-2.5 font-bold">#OPD-01</td>
                      <td className="p-2.5 font-medium">SyntheticFirst01 SyntheticLast01</td>
                      <td className="p-2.5">SYN-Cardiology</td>
                      <td className="p-2.5"><Badge className="bg-blue-600 text-white text-[10px]">Confirmed</Badge></td>
                      <td className="p-2.5">
                        <Button 
                          size="sm" 
                          variant="outline" 
                          onClick={() => handleProtectedAction("Nurse Desk", "/nurse")}
                          className="h-7 text-xs"
                        >
                          Check In
                        </Button>
                      </td>
                    </tr>
                    <tr>
                      <td className="p-2.5 font-bold">#OPD-02</td>
                      <td className="p-2.5 font-medium">SyntheticFirst02 SyntheticLast02</td>
                      <td className="p-2.5">SYN-Neurology</td>
                      <td className="p-2.5"><Badge className="bg-amber-600 text-white text-[10px]">Scheduled</Badge></td>
                      <td className="p-2.5">
                        <Button 
                          size="sm" 
                          variant="outline" 
                          onClick={() => handleProtectedAction("Nurse Desk", "/nurse")}
                          className="h-7 text-xs"
                        >
                          Check In
                        </Button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div className="pt-2 flex justify-end">
                <Button 
                  size="sm" 
                  onClick={() => handleProtectedAction("Nurse Desk", "/nurse")}
                  className="bg-blue-700 hover:bg-blue-800 text-white text-xs"
                >
                  Access Live Nurse Desk
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Tab: Diagnostic Lab Technician Preview */}
        {activeTab === "lab_technician" && (
          <Card className="border-slate-200 shadow-xs">
            <CardHeader>
              <CardTitle className="text-base">Diagnostic Laboratory Workstation</CardTitle>
              <CardDescription className="text-xs">
                Specimen accessioning, diagnostic worklists, and demographics-masked PMI verification
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="p-4 rounded-lg border border-slate-200 bg-white space-y-2">
                  <div className="text-xs font-bold text-slate-700">Specimen Accessioning</div>
                  <div className="text-sm font-semibold text-slate-900">Blood Chemistry Panel</div>
                  <div className="text-xs text-slate-500">Requisition: #LAB-2026-0812</div>
                  <Badge variant="outline" className="text-[10px] bg-blue-50 text-blue-700">Accessioned</Badge>
                </div>
                <div className="p-4 rounded-lg border border-slate-200 bg-white space-y-2">
                  <div className="text-xs font-bold text-slate-700">Demographics Scope</div>
                  <div className="text-sm font-semibold text-slate-900">Demographics Only Masking</div>
                  <div className="text-xs text-slate-500">Clinical notes strictly barred (HTTP 403)</div>
                  <Badge variant="outline" className="text-[10px] bg-emerald-50 text-emerald-700">Enforced</Badge>
                </div>
                <div className="p-4 rounded-lg border border-slate-200 bg-white space-y-2">
                  <div className="text-xs font-bold text-slate-700">Diagnostic Analyzer</div>
                  <div className="text-sm font-semibold text-slate-900">Direct LIS Interfacing</div>
                  <div className="text-xs text-slate-500">Telemetry Status: Connected</div>
                  <Badge variant="outline" className="text-[10px] bg-emerald-50 text-emerald-700">Online</Badge>
                </div>
              </div>
              <div className="pt-2 flex justify-end">
                <Button 
                  size="sm" 
                  onClick={() => handleProtectedAction("Laboratory Workstation", "/lab")}
                  className="bg-blue-700 hover:bg-blue-800 text-white text-xs"
                >
                  Access Live Laboratory
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Tab 2: Patient Portal Preview */}
        {activeTab === "patient" && (
          <Card className="border-slate-200 shadow-xs">
            <CardHeader>
              <CardTitle className="text-base">Patient Medical Timeline & Adherence</CardTitle>
              <CardDescription className="text-xs">
                Self-service appointment booking, care tasks, and verified 1:1 account security
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 rounded-lg border border-slate-200 bg-white space-y-2">
                  <div className="text-xs font-bold text-slate-700">Upcoming Visit</div>
                  <div className="text-sm font-semibold text-slate-900">Cardiology Consultation</div>
                  <div className="text-xs text-slate-500">Dr. Sarah Chen • Tomorrow 10:00 AM</div>
                  <Badge variant="outline" className="text-[10px] bg-blue-50 text-blue-700">Confirmed</Badge>
                </div>
                <div className="p-4 rounded-lg border border-slate-200 bg-white space-y-2">
                  <div className="text-xs font-bold text-slate-700">Medication Adherence</div>
                  <div className="text-sm font-semibold text-slate-900">Amlodipine 5mg (Oral)</div>
                  <div className="text-xs text-slate-500">Today: Dose Logged at 8:15 AM</div>
                  <Badge variant="outline" className="text-[10px] bg-emerald-50 text-emerald-700">Taken</Badge>
                </div>
                <div className="p-4 rounded-lg border border-slate-200 bg-white space-y-2">
                  <div className="text-xs font-bold text-slate-700">Patient Account Link</div>
                  <div className="text-sm font-semibold text-slate-900">1:1 Verified Binding</div>
                  <div className="text-xs text-slate-500">Auth Identity: patuser1@example.com</div>
                  <Badge variant="outline" className="text-[10px] bg-emerald-50 text-emerald-700">Active Link</Badge>
                </div>
              </div>
              <div className="pt-2 flex justify-end">
                <Button 
                  size="sm" 
                  onClick={() => handleProtectedAction("Patient Portal", "/portal")}
                  className="bg-blue-700 hover:bg-blue-800 text-white text-xs"
                >
                  Access Live Patient Portal
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Tab 4: Hospital Admin Preview */}
        {activeTab === "admin" && (
          <Card className="border-slate-200 shadow-xs">
            <CardHeader>
              <CardTitle className="text-base">Hospital Administration & Claims Analytics</CardTitle>
              <CardDescription className="text-xs">
                Revenue cycle metrics, automated insurance pre-authorization rules, and multi-tenant audit logs
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
                <div className="p-3 bg-slate-100 rounded-lg">
                  <div className="text-xs text-slate-500">Active Tenants</div>
                  <div className="text-xl font-bold text-slate-800">15 Branches</div>
                </div>
                <div className="p-3 bg-slate-100 rounded-lg">
                  <div className="text-xs text-slate-500">Claims Submitted</div>
                  <div className="text-xl font-bold text-blue-700">15 Claims</div>
                </div>
                <div className="p-3 bg-slate-100 rounded-lg">
                  <div className="text-xs text-slate-500">Pre-Auth Approval Rate</div>
                  <div className="text-xl font-bold text-emerald-700">92.4%</div>
                </div>
                <div className="p-3 bg-slate-100 rounded-lg">
                  <div className="text-xs text-slate-500">IoMT Defense Alarms</div>
                  <div className="text-xl font-bold text-slate-800">0 Active</div>
                </div>
              </div>
              <div className="pt-2 flex justify-end">
                <Button 
                  size="sm" 
                  onClick={() => handleProtectedAction("Admin Portal", "/admin")}
                  className="bg-blue-700 hover:bg-blue-800 text-white text-xs"
                >
                  Open Administrator Workstation
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </main>

      {/* Protected Action Interception Modal (AC-14.7) */}
      <Dialog open={interceptModalOpen} onOpenChange={setInterceptModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <div className="h-10 w-10 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center mb-2 mx-auto">
              <Lock className="h-5 w-5" />
            </div>
            <DialogTitle className="text-center text-lg">Workstation Authentication Required</DialogTitle>
            <DialogDescription className="text-center text-xs text-slate-600">
              Access to live clinical operations, document processing, and patient records requires verified authentication.
            </DialogDescription>
          </DialogHeader>

          <div className="p-3 rounded-lg border border-slate-200 bg-slate-50 text-xs text-slate-700 space-y-1">
            <div className="font-semibold text-slate-800">Target Workspace: {targetAction.title}</div>
            <p className="text-[11px] text-slate-500">
              You will be redirected to the authentication portal. You may choose any pre-configured synthetic demo role on the sign-in page to evaluate this workflow.
            </p>
          </div>

          <DialogFooter className="flex flex-col sm:flex-row gap-2">
            <Button variant="outline" size="sm" onClick={() => setInterceptModalOpen(false)}>
              Cancel
            </Button>
            <Button 
              size="sm" 
              className="bg-blue-700 hover:bg-blue-800 text-white font-semibold"
              onClick={() => router.push(`/login?returnUrl=${encodeURIComponent(targetAction.returnUrl)}`)}
            >
              Sign In to Continue
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

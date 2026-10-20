"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { 
  ShieldCheck, 
  Activity, 
  FileText, 
  Lock, 
  CheckCircle2, 
  ArrowRight, 
  Stethoscope, 
  Users, 
  Building2, 
  Sparkles,
  AlertTriangle
} from "lucide-react";

export default function RootHomePage() {
  const router = useRouter();
  const { user, isLoading } = useAuth();

  const getDashboardRoute = () => {
    if (!user) return "/login";
    switch (user.role) {
      case "hospital_admin": return "/admin";
      case "doctor": return "/doctor";
      case "nurse": return "/nurse";
      case "lab_technician": return "/lab";
      case "patient":
      default: return "/portal";
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-blue-50/30 text-slate-900 flex flex-col font-sans">
      {/* Top Navigation */}
      <header className="border-b border-slate-200/80 bg-white/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-y-0 gap-3">
            <div className="h-10 w-10 rounded-xl bg-blue-700 text-white font-black text-lg flex items-center justify-center shadow-md">
              CB
            </div>
            <div>
              <span className="font-extrabold text-lg tracking-tight text-slate-900">CareBridge AI</span>
              <span className="hidden sm:inline-block ml-2 text-[11px] font-semibold text-blue-700 bg-blue-50 border border-blue-200/60 px-2 py-0.5 rounded-full">
                Capstone Platform
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Link href="/demo">
              <Button variant="outline" size="sm" className="hidden sm:flex border-blue-200 text-blue-700 hover:bg-blue-50 font-medium">
                Guided Demo
              </Button>
            </Link>
            {user ? (
              <Button 
                onClick={() => router.push(getDashboardRoute())} 
                size="sm" 
                className="bg-blue-700 hover:bg-blue-800 text-white font-semibold shadow-xs"
              >
                Go to Workspace ({user.role})
              </Button>
            ) : (
              <Link href="/login">
                <Button size="sm" className="bg-blue-700 hover:bg-blue-800 text-white font-semibold shadow-xs">
                  Sign In
                </Button>
              </Link>
            )}
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="flex-1">
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-16 pb-20 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-50 border border-blue-200/80 text-blue-800 text-xs font-semibold mb-6 shadow-xs">
            <Sparkles className="h-3.5 w-3.5 text-blue-600" />
            <span>Autonomous Clinical Operations & Multi-Tenant Care Coordination</span>
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-slate-900 max-w-4xl mx-auto leading-tight">
            Safe, Verifiable AI for <br className="hidden sm:inline" />
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-700 to-indigo-600">
              Modern Hospital Healthcare
            </span>
          </h1>

          <p className="mt-6 text-base sm:text-lg text-slate-600 max-w-2xl mx-auto leading-relaxed">
            Integrating deep-learning IoMT security defense with zero-trust clinical workflows, OCR document extraction, tamper-evident prescriptions, and automated insurance claims.
          </p>

          {/* Dual Primary Call-to-Actions */}
          <div className="mt-8 flex flex-col sm:flex-row gap-4 justify-center items-center">
            <Link href="/demo" className="w-full sm:w-auto">
              <Button size="lg" className="w-full sm:w-auto bg-blue-700 hover:bg-blue-800 text-white font-bold px-8 shadow-md flex items-center justify-center gap-2">
                <span>Explore Guided Demo</span>
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link href="/login" className="w-full sm:w-auto">
              <Button size="lg" variant="outline" className="w-full sm:w-auto border-slate-300 text-slate-700 hover:bg-slate-100 font-semibold px-8">
                Sign In to Workstation
              </Button>
            </Link>
          </div>

          {/* Architecture Trust Badges */}
          <div className="mt-12 grid grid-cols-2 sm:grid-cols-4 gap-3 max-w-3xl mx-auto">
            <div className="p-3 rounded-lg border border-slate-200 bg-white/70 shadow-xs flex flex-col items-center">
              <span className="text-xl font-extrabold text-blue-700">17</span>
              <span className="text-xs font-medium text-slate-600">Database Tables (RLS)</span>
            </div>
            <div className="p-3 rounded-lg border border-slate-200 bg-white/70 shadow-xs flex flex-col items-center">
              <span className="text-xl font-extrabold text-indigo-700">SHA-256</span>
              <span className="text-xs font-medium text-slate-600">Prescription Hashes</span>
            </div>
            <div className="p-3 rounded-lg border border-slate-200 bg-white/70 shadow-xs flex flex-col items-center">
              <span className="text-xl font-extrabold text-emerald-700">17,727</span>
              <span className="text-xs font-medium text-slate-600">CSCM Research Files</span>
            </div>
            <div className="p-3 rounded-lg border border-slate-200 bg-white/70 shadow-xs flex flex-col items-center">
              <span className="text-xl font-extrabold text-amber-700">100%</span>
              <span className="text-xs font-medium text-slate-600">Synthetic Data Tested</span>
            </div>
          </div>
        </section>

        {/* Feature Highlights Grid */}
        <section className="bg-slate-50/80 border-y border-slate-200/80 py-16">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-3xl mx-auto mb-12">
              <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900">
                End-to-End Enterprise Hospital Platform
              </h2>
              <p className="mt-3 text-sm text-slate-600">
                CareBridge AI unifies front-desk OPD queuing, physician workstation tools, biomedical security, and patient self-service.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Feature 1 */}
              <Card className="border-slate-200/90 shadow-xs hover:shadow-md transition-shadow">
                <CardHeader>
                  <div className="h-10 w-10 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center mb-2">
                    <Activity className="h-5 w-5" />
                  </div>
                  <CardTitle className="text-base">CSCM-IoMT Defense</CardTitle>
                  <CardDescription className="text-xs">
                    Cross-Sensor Consistency Modeling detects subtle False Data Injection Attacks (FDIA) on medical monitors in real time.
                  </CardDescription>
                </CardHeader>
              </Card>

              {/* Feature 2 */}
              <Card className="border-slate-200/90 shadow-xs hover:shadow-md transition-shadow">
                <CardHeader>
                  <div className="h-10 w-10 rounded-lg bg-indigo-100 text-indigo-700 flex items-center justify-center mb-2">
                    <FileText className="h-5 w-5" />
                  </div>
                  <CardTitle className="text-base">Autonomous OCR Extraction</CardTitle>
                  <CardDescription className="text-xs">
                    Multimodal LLM pipeline ingests clinical lab PDFs and automatically extracts structured biomarkers with confidence scores.
                  </CardDescription>
                </CardHeader>
              </Card>

              {/* Feature 3 */}
              <Card className="border-slate-200/90 shadow-xs hover:shadow-md transition-shadow">
                <CardHeader>
                  <div className="h-10 w-10 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center mb-2">
                    <ShieldCheck className="h-5 w-5" />
                  </div>
                  <CardTitle className="text-base">Tamper-Evident Prescriptions</CardTitle>
                  <CardDescription className="text-xs">
                    Cryptographic SHA-256 prescription hashes allow patients and pharmacies to verify prescription authenticity without PHI leak.
                  </CardDescription>
                </CardHeader>
              </Card>
            </div>
          </div>
        </section>

        {/* Advisory Disclaimer Banner */}
        <section className="max-w-5xl mx-auto px-4 py-8">
          <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-4 flex items-start gap-3 text-amber-900 text-xs">
            <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold">Academic Capstone Research Prototype</span>
              <p className="mt-1 text-amber-800/90 leading-relaxed">
                CareBridge AI is designed and evaluated strictly for academic demonstration and research benchmarking. All patients, doctors, records, and telemetry shown are synthetic. This software is not certified under FDA 510(k), CDSCO, HIPAA Security Rule, or SOC 2 Type II audits.
              </p>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-6 text-center text-xs text-slate-500">
        <p>© 2026 CareBridge AI Capstone Project. SWE3004 / Final Capstone Packaging.</p>
      </footer>
    </div>
  );
}

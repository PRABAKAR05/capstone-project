"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth, SYNTHETIC_DEMO_ACCOUNTS, DemoAccount } from "@/lib/auth-context";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { ShieldCheck, UserCheck, Stethoscope, Lock, Mail } from "lucide-react";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const returnUrl = searchParams.get("returnUrl") || "/";

  const { signInWithEmail, selectDemoAccount, loginError, isLoading } = useAuth();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");

  const handleDemoSelect = (acc: DemoAccount) => {
    setEmail(acc.email);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;

    if (password) {
      const ok = await signInWithEmail(email, password);
      if (ok) router.push(returnUrl);
    } else {
      // In demonstration mode, allow proceeding with selected synthetic demo persona
      const demo = SYNTHETIC_DEMO_ACCOUNTS.find((a) => a.email === email);
      if (demo) {
        const ok = await selectDemoAccount(demo);
        if (ok) router.push(returnUrl);
      }
    }
  };

  return (
    <Card className="border-slate-200/90 shadow-lg">
      <CardHeader className="text-center pb-2">
        <CardTitle className="text-lg">Clinical Portal Authentication</CardTitle>
        <CardDescription>
          Sign in with your hospital credentials or select a verified synthetic demo role
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-5">
        {loginError && (
          <Alert variant="destructive">
            <AlertTitle>Authentication Failed</AlertTitle>
            <AlertDescription>{loginError}</AlertDescription>
          </Alert>
        )}

        {/* Quick Demonstration Persona Picker */}
        <div className="space-y-2 rounded-lg border border-blue-100 bg-blue-50/50 p-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-blue-900 flex items-center">
              <UserCheck className="h-3.5 w-3.5 mr-1.5 text-blue-700" />
              Demonstration Personas (Synthetic Test Accounts)
            </span>
            <span className="text-[10px] text-blue-600 font-mono">Open Source</span>
          </div>
          <p className="text-[11px] text-blue-800/80">
            Click a synthetic persona below to pre-fill test credentials. Zero production PII or secret keys are exposed.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 pt-1">
            {SYNTHETIC_DEMO_ACCOUNTS.map((acc) => (
              <button
                key={acc.email}
                type="button"
                onClick={() => handleDemoSelect(acc)}
                className={`text-left p-2 rounded-md border text-xs transition-all cursor-pointer ${
                  email === acc.email
                    ? "border-blue-600 bg-white shadow-xs font-bold text-blue-900"
                    : "border-slate-200/80 bg-white/70 hover:bg-white text-slate-700"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold">{acc.label}</span>
                  <Badge variant="outline" className="text-[9px] py-0 px-1">
                    {acc.role}
                  </Badge>
                </div>
                <div className="text-[10px] text-slate-500 truncate mt-0.5 font-mono">
                  {acc.email}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Standard Email/Password Form */}
        <form onSubmit={handleSubmit} className="space-y-3 pt-1">
          <div className="space-y-1">
            <label className="block text-xs font-semibold text-slate-700 flex items-center">
              <Mail className="h-3.5 w-3.5 mr-1 text-slate-400" />
              Account Email
            </label>
            <Input
              type="email"
              placeholder="name@hospital.example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <label className="block text-xs font-semibold text-slate-700 flex items-center">
                <Lock className="h-3.5 w-3.5 mr-1 text-slate-400" />
                Password
              </label>
              <span className="text-[11px] text-slate-400">Optional for demo personas</span>
            </div>
            <Input
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <Button
            type="submit"
            className="w-full mt-2 bg-blue-700 hover:bg-blue-800 text-white font-semibold"
            size="md"
            isLoading={isLoading}
          >
            Access Workstation
          </Button>
        </form>
      </CardContent>

      <CardFooter className="flex items-center justify-between text-[11px] text-slate-500 bg-slate-50/60 rounded-b-xl py-3 border-t border-slate-100">
        <span className="flex items-center">
          <ShieldCheck className="h-3.5 w-3.5 mr-1 text-emerald-600" />
          Role Level Security (RLS) Active
        </span>
        <span className="flex items-center">
          <Stethoscope className="h-3.5 w-3.5 mr-1 text-blue-600" />
          Asia/Kolkata Hospital Timezone
        </span>
      </CardFooter>
    </Card>
  );
}

export default function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-slate-100 via-blue-50/40 to-slate-100">
      <div className="w-full max-w-xl space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-blue-700 text-white font-black text-xl shadow-md">
            CB
          </div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
            CareBridge AI
          </h1>
          <p className="text-xs text-slate-600 max-w-sm mx-auto">
            Autonomous, AI-first clinical operations, patient engagement & multi-tenant care coordination
          </p>
        </div>

        <React.Suspense fallback={<div className="p-8 text-center text-xs text-slate-500">Loading workstation login...</div>}>
          <LoginForm />
        </React.Suspense>
      </div>
    </div>
  );
}

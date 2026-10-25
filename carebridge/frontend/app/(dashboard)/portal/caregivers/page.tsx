"use client";

import Link from "next/link";
import { Users, ShieldAlert, ArrowLeft } from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function PortalCaregiversPage() {
  return (
    <div className="max-w-2xl mx-auto py-8 px-4 space-y-6">
      <div className="flex items-center gap-2">
        <Link href="/portal">
          <Button variant="outline" size="sm" className="gap-1.5 text-xs text-slate-600">
            <ArrowLeft className="h-4 w-4" />
            Back to Patient Portal
          </Button>
        </Link>
      </div>

      <Card className="border-slate-200 shadow-sm">
        <CardHeader className="text-center pb-2">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-blue-50 text-blue-700 mb-2">
            <Users className="h-6 w-6" />
          </div>
          <CardTitle className="text-lg text-slate-900">Caregiver & Proxy Delegation</CardTitle>
          <CardDescription>
            Patient Health Records Privacy & Identity Verification Standard
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4 text-xs text-slate-600 leading-relaxed">
          <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-amber-900 flex items-start gap-2.5">
            <ShieldAlert className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-xs">In-Person Verification Required</p>
              <p className="text-[11px] text-amber-800 mt-0.5">
                To safeguard sensitive patient health information (PHI) and comply with statutory healthcare privacy mandates, proxy access delegation cannot be authorized through unverified online forms.
              </p>
            </div>
          </div>

          <div className="space-y-2 pt-1">
            <h4 className="font-bold text-slate-800">How to authorize a family caregiver or proxy:</h4>
            <ul className="list-disc pl-5 space-y-1.5 text-slate-600">
              <li>Visit the <strong>Hospital Front Desk or Medical Records Department</strong> in person.</li>
              <li>Present valid government-issued photo identification for both the patient and the designated caregiver.</li>
              <li>Sign the CareBridge Healthcare Proxy Authorization Consent document.</li>
              <li>Hospital staff will securely link the verified caregiver record to your patient ID within 24 hours.</li>
            </ul>
          </div>
        </CardContent>

        <CardFooter className="flex justify-center border-t border-slate-100 bg-slate-50/50 py-3 rounded-b-xl">
          <Link href="/portal">
            <Button size="sm" className="bg-blue-700 hover:bg-blue-800 text-white font-medium">
              Return to Patient Portal
            </Button>
          </Link>
        </CardFooter>
      </Card>
    </div>
  );
}

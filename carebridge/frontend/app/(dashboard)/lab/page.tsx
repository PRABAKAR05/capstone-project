"use client";

import * as React from "react";
import { useAuth } from "@/lib/auth-context";
import { apiFetch } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { FlaskConical, Search, ShieldCheck } from "lucide-react";

interface DemographicsMaskedPatient {
  id: string;
  mrn: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender: string;
  blood_group: string;
  phone: string;
}

export default function LabTechnicianPage() {
  const { hospital } = useAuth();
  const [searchQuery, setSearchQuery] = React.useState("");
  const [patients, setPatients] = React.useState<DemographicsMaskedPatient[]>([]);

  const handleSearch = React.useCallback(async (q: string) => {
    try {
      const endpoint = q ? `/patients?query=${encodeURIComponent(q)}` : "/patients";
      const data = await apiFetch<DemographicsMaskedPatient[]>(endpoint);
      setPatients(data || []);
    } catch {
      setPatients([]);
    }
  }, []);

  React.useEffect(() => {
    let isSubscribed = true;
    apiFetch<DemographicsMaskedPatient[]>("/patients")
      .then((data) => {
        if (isSubscribed) setPatients(data || []);
      })
      .catch(() => {
        if (isSubscribed) setPatients([]);
      });
    return () => {
      isSubscribed = false;
    };
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900 flex items-center">
            <FlaskConical className="h-5 w-5 mr-2 text-blue-700" />
            Diagnostic Laboratory Workstation
          </h1>
          <p className="text-xs text-slate-500">
            Specimen Accessioning, Diagnostic Testing, and Demographics-Masked PMI Verification
          </p>
        </div>
        <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200 text-xs">
          <ShieldCheck className="h-3.5 w-3.5 mr-1" />
          Demographics Masking Active
        </Badge>
      </div>

      <Card className="border-slate-200 shadow-xs">
        <CardHeader>
          <CardTitle className="text-base">Patient Demographics Verification (Specimen Labeling)</CardTitle>
          <CardDescription className="text-xs">
            Query patients by MRN to verify specimen tubes and requisition identifiers
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2 max-w-sm">
            <Input
              placeholder="Search by MRN or Name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="text-xs h-8"
            />
            <button
              onClick={() => handleSearch(searchQuery)}
              className="px-3 bg-blue-700 hover:bg-blue-800 text-white rounded-md text-xs font-medium flex items-center gap-1.5"
            >
              <Search className="h-3.5 w-3.5" />
              <span>Search</span>
            </button>
          </div>

          <div className="overflow-x-auto">
            <Table>
              <TableHeader className="bg-slate-50">
                <TableRow>
                  <TableHead className="text-xs">MRN</TableHead>
                  <TableHead className="text-xs">Full Name</TableHead>
                  <TableHead className="text-xs">DOB</TableHead>
                  <TableHead className="text-xs">Gender</TableHead>
                  <TableHead className="text-xs">Blood Group</TableHead>
                  <TableHead className="text-xs">Masking Scope</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {patients.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-6 text-xs text-slate-500">
                      No matching patient records found.
                    </TableCell>
                  </TableRow>
                ) : (
                  patients.map((p) => (
                    <TableRow key={p.id}>
                      <TableCell className="text-xs font-mono font-semibold">{p.mrn}</TableCell>
                      <TableCell className="text-xs">{p.first_name} {p.last_name}</TableCell>
                      <TableCell className="text-xs">{p.date_of_birth}</TableCell>
                      <TableCell className="text-xs capitalize">{p.gender}</TableCell>
                      <TableCell className="text-xs font-bold text-rose-700">{p.blood_group}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-[10px] bg-slate-50 text-slate-600">
                          Demographics Only
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

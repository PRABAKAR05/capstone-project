"use client";

import * as React from "react";
import { useAuth } from "@/lib/auth-context";
import { apiFetch } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Building2, Stethoscope, Users, Clock } from "lucide-react";
import { AdminAnalyticsView } from "@/components/analytics/admin-analytics-view";

interface Department {
  id: string;
  name: string;
  code: string;
  head_of_department?: string;
}

interface Doctor {
  id: string;
  full_name: string;
  specialization: string;
  qualification: string;
  license_number: string;
  consultation_fee: number;
  is_available: boolean;
}

export default function AdminOperationsPage() {
  const { hospital } = useAuth();
  const [departments, setDepartments] = React.useState<Department[]>([]);
  const [doctors, setDoctors] = React.useState<Doctor[]>([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const [deptData, docData] = await Promise.all([
          apiFetch<Department[]>("/departments"),
          apiFetch<Doctor[]>("/doctors"),
        ]);
        setDepartments(deptData || []);
        setDoctors(docData || []);
      } catch {
        // Mock fallback with the 4 active hospital physicians
        setDepartments([
          { id: "1", name: "Cardiology", code: "CARD", head_of_department: "Dr. Evelyn Reed" },
          { id: "2", name: "Neurology", code: "NEUR", head_of_department: "Dr. Marcus Thorne" },
        ]);
        setDoctors([
          {
            id: "90000000-0022-0000-0000-000000000001",
            full_name: "Dr. Evelyn Reed",
            specialization: "Cardiology",
            qualification: "MD, FACC",
            license_number: "LIC-PH3-DOC1",
            consultation_fee: 500,
            is_available: true,
          },
          {
            id: "90000000-0022-0000-0000-000000000002",
            full_name: "Dr. Marcus Thorne",
            specialization: "Neurology",
            qualification: "MBBS, MD, DM",
            license_number: "LIC-PH3-DOC2",
            consultation_fee: 600,
            is_available: true,
          },
          {
            id: "90000000-0022-0000-0000-000000000003",
            full_name: "Dr. Clara Oswald",
            specialization: "General Medicine",
            qualification: "MBBS, MD",
            license_number: "LIC-PH3-DOC3",
            consultation_fee: 400,
            is_available: true,
          },
          {
            id: "71111111-1111-1111-1111-111111111111",
            full_name: "Dr. Rajesh Nair",
            specialization: "Cardiology",
            qualification: "MD",
            license_number: "LIC-PH3-DOC4",
            consultation_fee: 500,
            is_available: true,
          },
        ]);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  return (
    <div className="space-y-6">
      <div className="border-b border-slate-200 pb-4">
        <h1 className="text-xl font-bold tracking-tight text-slate-900 flex items-center">
          <Building2 className="h-5 w-5 mr-2 text-blue-700" />
          Hospital Operations & Governance Overview
        </h1>
        <p className="text-xs text-slate-500">
          Tenant Parameters, Department Architecture & Active Medical Staff Roster
        </p>
      </div>
 
      {/* Real-time Hospital Operations Analytics Dashboard (Phase 11) */}
      <AdminAnalyticsView />

      {/* Operational Metrics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="border-blue-100 bg-blue-50/40">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-[10px] font-bold uppercase text-slate-500">Hospital Facility</p>
              <h4 className="text-sm font-bold text-slate-900 mt-0.5">{hospital?.name || "Aegis Metro"}</h4>
              <p className="text-[10px] text-blue-700 mt-1">Tenant ID: 11111111...1111</p>
            </div>
            <Building2 className="h-7 w-7 text-blue-600 opacity-80" />
          </CardContent>
        </Card>

        <Card className="border-teal-100 bg-teal-50/40">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-[10px] font-bold uppercase text-slate-500">Active Departments</p>
              {loading ? (
                <div className="h-6 w-20 bg-teal-200/60 rounded animate-pulse my-1" />
              ) : (
                <h4 className="text-lg font-extrabold text-teal-900 mt-0.5">{departments.length} Units</h4>
              )}
              <p className="text-[10px] text-teal-700 mt-1">100% Operational</p>
            </div>
            <Stethoscope className="h-7 w-7 text-teal-600 opacity-80" />
          </CardContent>
        </Card>

        <Card className="border-slate-200 bg-white">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-[10px] font-bold uppercase text-slate-500">Active Physicians</p>
              {loading ? (
                <div className="h-6 w-24 bg-slate-200 rounded animate-pulse my-1" />
              ) : (
                <h4 className="text-lg font-extrabold text-slate-900 mt-0.5">{doctors.length} Doctors</h4>
              )}
              <p className="text-[10px] text-emerald-600 font-semibold mt-1">On-Duty & Ready</p>
            </div>
            <Users className="h-7 w-7 text-slate-600 opacity-80" />
          </CardContent>
        </Card>

        <Card className="border-slate-200 bg-white">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-[10px] font-bold uppercase text-slate-500">Facility Timezone</p>
              <h4 className="text-sm font-bold text-slate-900 mt-0.5">{hospital?.timezone || "Asia/Kolkata"}</h4>
              <p className="text-[10px] text-slate-500 mt-1">IANA Standard</p>
            </div>
            <Clock className="h-7 w-7 text-slate-400 opacity-80" />
          </CardContent>
        </Card>
      </div>

      {/* Departments Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Clinical Departments</CardTitle>
          <CardDescription>
            Organized medical service divisions within this facility
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Code</TableHead>
                <TableHead>Department Name</TableHead>
                <TableHead>Head of Department</TableHead>
                <TableHead className="text-right">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {departments.map((dept) => (
                <TableRow key={dept.id}>
                  <TableCell className="font-mono text-xs font-bold text-blue-800">
                    {dept.code}
                  </TableCell>
                  <TableCell className="font-semibold text-xs text-slate-900">
                    {dept.name}
                  </TableCell>
                  <TableCell className="text-xs text-slate-600">
                    {dept.head_of_department || "Staff Physician"}
                  </TableCell>
                  <TableCell className="text-right">
                    <Badge variant="success">Active</Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Doctor Roster Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Medical Staff & Doctor Roster</CardTitle>
          <CardDescription>
            Licensed physicians configured for appointment booking and clinical care
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Doctor Name</TableHead>
                <TableHead>Specialization</TableHead>
                <TableHead>License #</TableHead>
                <TableHead>Qualifications</TableHead>
                <TableHead>Consultation Fee</TableHead>
                <TableHead className="text-right">Availability</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {doctors.map((doc) => (
                <TableRow key={doc.id}>
                  <TableCell className="font-semibold text-xs text-slate-900">
                    {doc.full_name}
                  </TableCell>
                  <TableCell className="text-xs text-blue-700 font-medium">
                    {doc.specialization}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-slate-500">
                    {doc.license_number}
                  </TableCell>
                  <TableCell className="text-xs text-slate-600">{doc.qualification}</TableCell>
                  <TableCell className="text-xs font-extrabold text-slate-900">
                    ₹{doc.consultation_fee}
                  </TableCell>
                  <TableCell className="text-right">
                    {doc.is_available ? (
                      <Badge variant="teal">Available for Slots</Badge>
                    ) : (
                      <Badge variant="outline">On Leave</Badge>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

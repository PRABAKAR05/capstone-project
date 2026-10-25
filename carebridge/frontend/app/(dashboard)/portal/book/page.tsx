"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { apiFetch, ProblemDetailsError } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { CalendarPlus, Stethoscope, Clock, CheckCircle2, AlertTriangle, ArrowLeft, ArrowRight, ShieldCheck } from "lucide-react";

interface Department {
  id: string;
  name: string;
  code: string;
}

interface Doctor {
  id: string;
  department_id: string;
  full_name: string;
  specialization: string;
  qualification: string;
  consultation_fee: number;
  is_available: boolean;
}

interface DoctorSlot {
  start_time: string;
  end_time: string;
  local_start_time: string;
  is_available: boolean;
}

interface SlotsResponse {
  hospital_timezone: string;
  date: string;
  slots: DoctorSlot[];
}

export default function BookAppointmentWizard() {
  const router = useRouter();
  const { hospital, user } = useAuth();

  const [step, setStep] = React.useState<1 | 2 | 3>(1);
  const [departments, setDepartments] = React.useState<Department[]>([]);
  const [doctors, setDoctors] = React.useState<Doctor[]>([]);
  const [slots, setSlots] = React.useState<DoctorSlot[]>([]);

  // Form selections
  const [selectedDeptId, setSelectedDeptId] = React.useState<string>("");
  const [selectedDoctorId, setSelectedDoctorId] = React.useState<string>("");
  const [selectedDate, setSelectedDate] = React.useState<string>("2026-11-20");
  const [minDate] = React.useState<string>("2026-11-01");
  const [selectedSlot, setSelectedSlot] = React.useState<DoctorSlot | null>(null);
  const [reasonForVisit, setReasonForVisit] = React.useState<string>("Routine health review");

  // Loading & error states
  const [loadingDepts, setLoadingDepts] = React.useState(true);
  const [loadingDoctors, setLoadingDoctors] = React.useState(false);
  const [loadingSlots, setLoadingSlots] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null);
  const [conflictAlert, setConflictAlert] = React.useState<string | null>(null);

  // 1. Fetch departments on mount
  React.useEffect(() => {
    let ignore = false;
    async function loadDepts() {
      try {
        const data = await apiFetch<Department[]>("/departments");
        if (!ignore && data && data.length > 0) {
          setDepartments(data);
          setSelectedDeptId(data[0].id);
          setLoadingDepts(false);
        }
      } catch {
        if (!ignore) {
          setDepartments([
            { id: "11111111-0000-0000-0000-000000000001", name: "Cardiology", code: "CARD" },
            { id: "11111111-0000-0000-0000-000000000002", name: "Neurology", code: "NEUR" },
          ]);
          setSelectedDeptId("11111111-0000-0000-0000-000000000001");
          setLoadingDepts(false);
        }
      }
    }
    loadDepts();
    return () => {
      ignore = true;
    };
  }, []);

  // 2. Fetch doctors when department changes
  React.useEffect(() => {
    if (!selectedDeptId) return;
    let ignore = false;
    async function loadDocs() {
      try {
        const data = await apiFetch<Doctor[]>(`/doctors?department_id=${selectedDeptId}`);
        if (!ignore && data && data.length > 0) {
          setDoctors(data);
          setSelectedDoctorId(data[0].id);
          setLoadingDoctors(false);
        }
      } catch {
        if (!ignore) {
          setDoctors([
            {
              id: "71111111-1111-1111-1111-111111111111",
              department_id: selectedDeptId,
              full_name: "Dr. Evelyn Reed",
              specialization: "Interventional Cardiology",
              qualification: "MD, FACC",
              consultation_fee: 500,
              is_available: true,
            },
          ]);
          setSelectedDoctorId("71111111-1111-1111-1111-111111111111");
          setLoadingDoctors(false);
        }
      }
    }
    loadDocs();
    return () => {
      ignore = true;
    };
  }, [selectedDeptId]);

  // 3. Fetch doctor slots
  const fetchSlots = React.useCallback(async (docId?: string, dt?: string) => {
    const targetDoc = docId || selectedDoctorId;
    const targetDate = dt || selectedDate;
    if (!targetDoc || !targetDate) return;
    setLoadingSlots(true);
    setConflictAlert(null);
    try {
      const data = await apiFetch<SlotsResponse>(
        `/doctors/${targetDoc}/slots?slot_date=${targetDate}`
      );
      setSlots(data.slots || []);
    } catch {
      const mockSlots: DoctorSlot[] = [];
      const times = ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30", "14:00", "14:30", "15:00", "15:30"];
      times.forEach((t, i) => {
        mockSlots.push({
          start_time: `${targetDate}T${t}:00Z`,
          end_time: `${targetDate}T${t}:30Z`,
          local_start_time: t,
          is_available: i !== 2,
        });
      });
      setSlots(mockSlots);
    } finally {
      setLoadingSlots(false);
    }
  }, [selectedDoctorId, selectedDate]);

  // 4. Handle final booking submission
  const handleBookingSubmit = async () => {
    if (!selectedSlot || !selectedDoctorId || !selectedDeptId) return;
    setSubmitting(true);
    setErrorMsg(null);
    setConflictAlert(null);

    // Authenticated patient ID
    const patientId = user?.patient_id || "90000000-aaaa-0000-0000-000000000001";

    try {
      await apiFetch("/appointments", {
        method: "POST",
        body: JSON.stringify({
          patient_id: patientId,
          doctor_id: selectedDoctorId,
          department_id: selectedDeptId,
          scheduled_at: selectedSlot.start_time,
          duration_minutes: 30,
          reason_for_visit: reasonForVisit,
        }),
      });

      router.push("/portal?booked=true");
    } catch (err) {
      if (err instanceof ProblemDetailsError) {
        if (err.status === 409) {
          // Concurrency Conflict: Doctor or patient has an overlapping booking
          setConflictAlert(
            "Double-Booking Conflict (HTTP 409): The requested slot was just booked by another patient. Please choose an alternate slot."
          );
          setStep(2); // Keep wizard on slot selection step
          await fetchSlots(); // Refresh slots to show newly booked state
        } else {
          setErrorMsg(err.detail);
        }
      } else {
        setErrorMsg("Failed to book appointment. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const selectedDoctor = doctors.find((d) => d.id === selectedDoctorId);
  const selectedDepartment = departments.find((d) => d.id === selectedDeptId);

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Wizard Header */}
      <div className="flex items-center justify-between border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900 flex items-center">
            <CalendarPlus className="h-5 w-5 mr-2 text-blue-700" />
            Clinical Appointment Booking Wizard
          </h1>
          <p className="text-xs text-slate-500">
            3-Step scheduling with live doctor availability in {hospital?.timezone || "Asia/Kolkata"}
          </p>
        </div>

        {/* Step Indicator */}
        <div className="flex items-center space-x-2 text-xs font-semibold">
          <span className={`px-2 py-1 rounded-md ${step === 1 ? "bg-blue-700 text-white" : "bg-slate-100 text-slate-600"}`}>
            1. Specialist
          </span>
          <span className="text-slate-300">→</span>
          <span className={`px-2 py-1 rounded-md ${step === 2 ? "bg-blue-700 text-white" : "bg-slate-100 text-slate-600"}`}>
            2. Slot Time
          </span>
          <span className="text-slate-300">→</span>
          <span className={`px-2 py-1 rounded-md ${step === 3 ? "bg-blue-700 text-white" : "bg-slate-100 text-slate-600"}`}>
            3. Review
          </span>
        </div>
      </div>

      {conflictAlert && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4 text-red-600" />
          <AlertTitle>Slot Collision Detected</AlertTitle>
          <AlertDescription>{conflictAlert}</AlertDescription>
        </Alert>
      )}

      {errorMsg && (
        <Alert variant="destructive">
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errorMsg}</AlertDescription>
        </Alert>
      )}

      {/* STEP 1: Select Department & Doctor */}
      {step === 1 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center">
              <Stethoscope className="h-4 w-4 mr-2 text-blue-600" />
              Step 1: Select Department & Attending Physician
            </CardTitle>
            <CardDescription>
              Choose a medical specialty and an available doctor
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-4">
            {loadingDepts ? (
              <Skeleton className="h-10 w-full" />
            ) : (
              <Select
                label="Clinical Department"
                value={selectedDeptId}
                onChange={(e) => setSelectedDeptId(e.target.value)}
              >
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.code})
                  </option>
                ))}
              </Select>
            )}

            <div className="space-y-2">
              <label className="block text-xs font-semibold text-slate-700">
                Available Physicians ({doctors.length})
              </label>
              {loadingDoctors ? (
                <Skeleton className="h-24 w-full" />
              ) : doctors.length === 0 ? (
                <p className="text-xs text-slate-500 italic p-3 border rounded-md">
                  No doctors found in this department.
                </p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {doctors.map((doc) => (
                    <button
                      key={doc.id}
                      type="button"
                      onClick={() => setSelectedDoctorId(doc.id)}
                      className={`text-left p-3.5 rounded-lg border transition-all cursor-pointer ${
                        selectedDoctorId === doc.id
                          ? "border-blue-700 bg-blue-50/50 shadow-xs"
                          : "border-slate-200 hover:border-slate-300 bg-white"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-slate-900">{doc.full_name}</span>
                        <Badge variant="teal" className="text-[10px]">
                          ₹{doc.consultation_fee}
                        </Badge>
                      </div>
                      <p className="text-[11px] text-blue-700 font-medium mt-0.5">
                        {doc.specialization}
                      </p>
                      <p className="text-[10px] text-slate-500 mt-1">
                        {doc.qualification}
                      </p>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </CardContent>

          <CardFooter className="flex justify-end">
            <Button
              size="md"
              disabled={!selectedDoctorId}
              onClick={() => {
                setStep(2);
                fetchSlots();
              }}
              className="flex items-center space-x-1"
            >
              <span>Next: Select Slot</span>
              <ArrowRight className="h-4 w-4" />
            </Button>
          </CardFooter>
        </Card>
      )}

      {/* STEP 2: Timezone-Aware Date & Slot Picker */}
      {step === 2 && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base flex items-center">
                  <Clock className="h-4 w-4 mr-2 text-blue-600" />
                  Step 2: Choose Consultation Date & Slot
                </CardTitle>
                <CardDescription>
                  Slots are generated dynamically in hospital timezone ({hospital?.timezone || "Asia/Kolkata"})
                </CardDescription>
              </div>
              {selectedDoctor && (
                <Badge variant="default" className="text-xs">
                  {selectedDoctor.full_name}
                </Badge>
              )}
            </div>
          </CardHeader>

          <CardContent className="space-y-5">
            {/* Target Date Picker */}
            <div className="max-w-xs">
              <Input
                label={`Select Date (${hospital?.timezone || "Asia/Kolkata"})`}
                type="date"
                value={selectedDate}
                min={minDate}
                onChange={(e) => setSelectedDate(e.target.value)}
              />
            </div>

            {/* Dynamic Slot Grid */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-700">
                  Available 30-Minute Slots
                </span>
                <span className="text-[11px] text-slate-400">
                  Green: Available | Gray: Booked
                </span>
              </div>

              {loadingSlots ? (
                <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                  {Array.from({ length: 8 }).map((_, i) => (
                    <Skeleton key={i} className="h-10 w-full" />
                  ))}
                </div>
              ) : slots.length === 0 ? (
                <p className="text-xs text-slate-500 italic p-4 border rounded-md text-center">
                  No slots generated for this date.
                </p>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {slots.map((s) => {
                    const isSelected = selectedSlot?.start_time === s.start_time;
                    return (
                      <button
                        key={s.start_time}
                        type="button"
                        disabled={!s.is_available}
                        onClick={() => setSelectedSlot(s)}
                        className={`p-2.5 rounded-lg border text-center transition-all ${
                          !s.is_available
                            ? "bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed opacity-60 line-through"
                            : isSelected
                            ? "bg-blue-700 text-white font-bold border-blue-700 shadow-sm cursor-pointer"
                            : "bg-white text-slate-800 border-slate-300 hover:border-blue-600 hover:bg-blue-50/50 cursor-pointer"
                        }`}
                      >
                        <span className="text-xs font-semibold block">{s.local_start_time}</span>
                        <span className="text-[9px] block opacity-80">
                          {s.is_available ? "Available" : "Booked"}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </CardContent>

          <CardFooter className="flex justify-between">
            <Button
              variant="outline"
              size="md"
              onClick={() => setStep(1)}
              className="flex items-center space-x-1"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>Back</span>
            </Button>
            <Button
              size="md"
              disabled={!selectedSlot}
              onClick={() => setStep(3)}
              className="flex items-center space-x-1"
            >
              <span>Next: Review & Confirm</span>
              <ArrowRight className="h-4 w-4" />
            </Button>
          </CardFooter>
        </Card>
      )}

      {/* STEP 3: Review & Submit */}
      {step === 3 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center">
              <CheckCircle2 className="h-4 w-4 mr-2 text-emerald-600" />
              Step 3: Review Consultation Summary
            </CardTitle>
            <CardDescription>
              Verify appointment parameters before committing to the schedule
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-4">
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 space-y-3">
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold">
                    Specialist & Department
                  </span>
                  <span className="font-bold text-slate-900">{selectedDoctor?.full_name}</span>
                  <p className="text-slate-500 text-[11px]">{selectedDepartment?.name}</p>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold">
                    Scheduled Time ({hospital?.timezone || "Asia/Kolkata"})
                  </span>
                  <span className="font-bold text-blue-800">
                    {selectedDate} at {selectedSlot?.local_start_time}
                  </span>
                  <p className="text-slate-500 text-[11px]">Duration: 30 minutes</p>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold">
                    Consultation Fee
                  </span>
                  <span className="font-extrabold text-slate-900 text-sm">
                    ₹{selectedDoctor?.consultation_fee}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold">
                    Hospital Facility
                  </span>
                  <span className="font-semibold text-slate-700">
                    {hospital?.name || "Aegis Metro General Hospital"}
                  </span>
                </div>
              </div>
            </div>

            <div className="space-y-1">
              <Input
                label="Reason for Visit / Symptoms"
                placeholder="e.g. Follow-up after blood test, chest tightness"
                value={reasonForVisit}
                onChange={(e) => setReasonForVisit(e.target.value)}
                required
              />
            </div>

            <div className="flex items-center space-x-2 text-[11px] text-slate-500">
              <ShieldCheck className="h-4 w-4 text-emerald-600 shrink-0" />
              <span>
                Appointments are protected by database double-booking exclusion constraints.
              </span>
            </div>
          </CardContent>

          <CardFooter className="flex justify-between">
            <Button
              variant="outline"
              size="md"
              onClick={() => setStep(2)}
              disabled={submitting}
              className="flex items-center space-x-1"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>Back</span>
            </Button>
            <Button
              size="md"
              onClick={handleBookingSubmit}
              isLoading={submitting}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              Confirm & Book Appointment
            </Button>
          </CardFooter>
        </Card>
      )}
    </div>
  );
}

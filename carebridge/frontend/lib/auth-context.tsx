"use client";

import * as React from "react";
import { supabase, setActiveDemoToken, apiFetch, API_BASE_URL } from "@/lib/api";

export type UserRole = "hospital_admin" | "doctor" | "nurse" | "lab_technician" | "patient";

export interface UserProfile {
  id: string;
  hospital_id: string;
  role: UserRole;
  full_name: string;
  email: string;
  patient_id?: string;
}

export interface HospitalInfo {
  id: string;
  name: string;
  slug: string;
  timezone: string;
}

export interface DemoAccount {
  label: string;
  email: string;
  role: UserRole;
  description: string;
  password?: string;
}

export const SYNTHETIC_DEMO_ACCOUNTS: DemoAccount[] = [
  {
    label: "Hospital Administrator",
    email: "cb-admin-01@carebridge.test",
    role: "hospital_admin",
    description: "Full administrative governance, capacity monitoring, and doctor roster overview.",
    password: "156ZFZHgEc^fWYi&",
  },
  {
    label: "Attending Cardiologist",
    email: "cb-doctor-01@carebridge.test",
    role: "doctor",
    description: "Doctor workstation, patient queue, and authorized clinical notes recording.",
    password: "o8cXDQ1jVP6*0MzT",
  },
  {
    label: "Lead Clinical Nurse",
    email: "cb-nurse-01@carebridge.test",
    role: "nurse",
    description: "Patient intake desk, rapid OPD check-in, and care coordination task execution.",
    password: "bOBNl#WaF4LaL!9K",
  },
  {
    label: "Diagnostic Lab Technician",
    email: "cb-lab-01@carebridge.test",
    role: "lab_technician",
    description: "Diagnostic orders, specimen accessioning, and demographics-masked patient verification.",
    password: "9T^L9ue6SYWYVJEq",
  },
  {
    label: "Authoritative Patient",
    email: "cb-patient-01@carebridge.test",
    role: "patient",
    description: "Self records, 3-step appointment booking wizard, and medication adherence.",
    password: "Z5RIVfS^SEyhW5li",
  },
];

interface AuthContextType {
  user: UserProfile | null;
  hospital: HospitalInfo | null;
  isLoading: boolean;
  loginError: string | null;
  signInWithEmail: (email: string, password: string) => Promise<boolean>;
  selectDemoAccount: (account: DemoAccount, password?: string) => Promise<boolean>;
  signOut: () => Promise<void>;
  refreshHospital: () => Promise<void>;
}

const AuthContext = React.createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<UserProfile | null>(null);
  const [hospital, setHospital] = React.useState<HospitalInfo | null>(null);
  const [isLoading, setIsLoading] = React.useState<boolean>(true);
  const [loginError, setLoginError] = React.useState<string | null>(null);

  const fetchHospitalDetails = React.useCallback(async () => {
    try {
      const data = await apiFetch<HospitalInfo>("/hospitals/me");
      setHospital(data);
    } catch {
      // Fallback display if hospital lookup fails
      setHospital({
        id: "11111111-1111-1111-1111-111111111111",
        name: "Aegis Metro General Hospital",
        slug: "aegis-metro",
        timezone: "Asia/Kolkata",
      });
    }
  }, []);

  const loadUserProfile = React.useCallback(async (userId: string, email: string) => {
    try {
      const { data: profile } = await supabase
        .from("profiles")
        .select("id, hospital_id, role, full_name, email")
        .eq("id", userId)
        .single();

      if (profile) {
        setUser({
          id: profile.id,
          hospital_id: profile.hospital_id,
          role: profile.role as UserRole,
          full_name: profile.full_name,
          email: profile.email || email,
        });
      } else {
        // Default patient fallback profile if database has not populated yet
        setUser({
          id: userId,
          hospital_id: "11111111-1111-1111-1111-111111111111",
          role: "patient",
          full_name: "Patient User",
          email,
        });
      }
      await fetchHospitalDetails();
    } catch {
      setUser({
        id: userId,
        hospital_id: "11111111-1111-1111-1111-111111111111",
        role: "patient",
        full_name: "Patient User",
        email,
      });
    }
  }, [fetchHospitalDetails]);

  const signInWithEmail = React.useCallback(async (email: string, pass: string): Promise<boolean> => {
    setIsLoading(true);
    setLoginError(null);
    try {
      // 1. Try native backend FastAPI auth first (validates against PostgreSQL auth.users)
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: email.trim(), password: pass }),
        });

        if (res.ok) {
          const data = await res.json();
          setActiveDemoToken(data.access_token);
          setUser({
            id: data.user.id,
            hospital_id: data.user.hospital_id,
            role: data.user.role as UserRole,
            full_name: data.user.full_name,
            email: data.user.email,
            patient_id: data.user.patient_id ? String(data.user.patient_id) : undefined,
          });
          await fetchHospitalDetails();
          return true;
        } else {
          const errData = await res.json().catch(() => ({}));
          let errMsg = "Invalid email or password";
          if (errData.detail) {
            if (typeof errData.detail === "string") {
              errMsg = errData.detail;
            } else if (Array.isArray(errData.detail)) {
              errMsg = errData.detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join(", ");
            } else if (typeof errData.detail === "object") {
              errMsg = errData.title || JSON.stringify(errData.detail);
            }
          }
          setLoginError(errMsg);
          return false;
        }
      } catch {
        // Fallback to Supabase auth if backend endpoint is unreachable
      }

      // 2. Fallback to Supabase Cloud Auth
      try {
        const { data, error } = await supabase.auth.signInWithPassword({
          email: email.trim(),
          password: pass,
        });
        if (!error && data?.user) {
          await loadUserProfile(data.user.id, data.user.email || email);
          return true;
        } else if (error) {
          setLoginError(error.message);
          return false;
        }
      } catch {
        // Supabase error
      }

      setLoginError("Invalid email or password");
      return false;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Authentication error";
      setLoginError(msg);
      return false;
    } finally {
      setIsLoading(false);
    }
  }, [fetchHospitalDetails, loadUserProfile]);

  // Initial session check
  React.useEffect(() => {
    async function initSession() {
      setIsLoading(true);
      try {
        // 1. Check for stored JWT token from native backend
        const savedToken = typeof window !== "undefined" ? localStorage.getItem("carebridge_auth_token") : null;
        if (savedToken) {
          setActiveDemoToken(savedToken);
          try {
            const res = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
              headers: { Authorization: `Bearer ${savedToken}` },
            });
            if (res.ok) {
              const me = await res.json();
              setUser({
                id: me.id,
                hospital_id: me.hospital_id,
                role: me.role as UserRole,
                full_name: me.full_name,
                email: me.email,
              });
              await fetchHospitalDetails();
              setIsLoading(false);
              return;
            }
          } catch {
            // Token expired or server unreachable, fallback below
          }
        }

        // 2. Check Supabase session
        const { data } = await supabase.auth.getSession();
        if (data.session?.user) {
          await loadUserProfile(data.session.user.id, data.session.user.email || "");
          setIsLoading(false);
          return;
        }

        // 3. Fallback to saved demo persona
        const savedDemo = typeof window !== "undefined" ? localStorage.getItem("carebridge_demo_account") : null;
        if (savedDemo) {
          const acc = JSON.parse(savedDemo) as DemoAccount;
          const fullAcc = SYNTHETIC_DEMO_ACCOUNTS.find((a) => a.email === acc.email) || acc;
          if (fullAcc.password) {
            const ok = await signInWithEmail(fullAcc.email, fullAcc.password);
            if (ok) return;
          }

          const uid = acc.role === "doctor"
            ? "90000000-0002-0000-0000-000000000001"
            : acc.role === "nurse"
            ? "11111111-0003-0000-0000-000000000032"
            : acc.role === "lab_technician"
            ? "11111111-0003-0000-0000-000000000030"
            : acc.role === "patient"
            ? "70000000-0000-0000-0000-000000000004"
            : "70000000-0000-0000-0000-000000000001";

          setUser({
            id: uid,
            hospital_id: "11111111-1111-1111-1111-111111111111",
            role: acc.role,
            full_name: acc.label,
            email: acc.email,
          });
          await fetchHospitalDetails();
        }
      } catch {
        // Session initialization completed
      } finally {
        setIsLoading(false);
      }
    }
    initSession();
  }, [loadUserProfile, fetchHospitalDetails, signInWithEmail]);

  const selectDemoAccount = async (account: DemoAccount, pass?: string): Promise<boolean> => {
    setIsLoading(true);
    setLoginError(null);
    try {
      const effectivePassword = pass || account.password;
      if (effectivePassword) {
        const success = await signInWithEmail(account.email, effectivePassword);
        if (success) {
          if (typeof window !== "undefined") {
            localStorage.setItem("carebridge_demo_account", JSON.stringify(account));
          }
          return true;
        }
      }
      // Demo simulation switch
      const uid = account.role === "doctor"
        ? "90000000-0002-0000-0000-000000000001"
        : account.role === "nurse"
        ? "11111111-0003-0000-0000-000000000032"
        : account.role === "lab_technician"
        ? "11111111-0003-0000-0000-000000000030"
        : account.role === "patient"
        ? "90000000-0005-0000-0000-000000000001"
        : "70000000-0000-0000-0000-000000000001";

      const patientId = account.role === "patient" ? "90000000-aaaa-0000-0000-000000000001" : undefined;

      setUser({
        id: uid,
        hospital_id: "11111111-1111-1111-1111-111111111111",
        role: account.role,
        full_name: account.label,
        email: account.email,
        patient_id: patientId,
      });
      if (typeof window !== "undefined") {
        localStorage.setItem("carebridge_demo_account", JSON.stringify(account));
      }
      await fetchHospitalDetails();
      return true;
    } catch {
      setLoginError("Failed to switch demonstration persona");
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  const signOut = async () => {
    setIsLoading(true);
    try {
      await supabase.auth.signOut();
      if (typeof window !== "undefined") {
        localStorage.removeItem("carebridge_demo_account");
        localStorage.removeItem("carebridge_auth_token");
      }
      setActiveDemoToken(null);
      setUser(null);
      setHospital(null);
      if (typeof window !== "undefined") {
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.href = "/login";
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        hospital,
        isLoading,
        loginError,
        signInWithEmail,
        selectDemoAccount,
        signOut,
        refreshHospital: fetchHospitalDetails,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = React.useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

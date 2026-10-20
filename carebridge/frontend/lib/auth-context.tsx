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
}

export const SYNTHETIC_DEMO_ACCOUNTS: DemoAccount[] = [
  {
    label: "Hospital Administrator",
    email: "admin1@aegis.example.com",
    role: "hospital_admin",
    description: "Full administrative governance, capacity monitoring, and doctor roster overview.",
  },
  {
    label: "Attending Cardiologist",
    email: "doc1@aegis.example.com",
    role: "doctor",
    description: "Doctor workstation, patient queue, and authorized clinical notes recording.",
  },
  {
    label: "Lead Clinical Nurse",
    email: "nurse.sarah@aegis.health",
    role: "nurse",
    description: "Patient intake desk, rapid OPD check-in, and care coordination task execution.",
  },
  {
    label: "Diagnostic Lab Technician",
    email: "lab.marcus@aegis.health",
    role: "lab_technician",
    description: "Diagnostic orders, specimen accessioning, and demographics-masked patient verification.",
  },
  {
    label: "Authoritative Patient",
    email: "patuser1@example.com",
    role: "patient",
    description: "Self records, 3-step appointment booking wizard, and medication adherence.",
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

  // Initial session check
  React.useEffect(() => {
    async function initSession() {
      setIsLoading(true);
      try {
        const { data } = await supabase.auth.getSession();
        if (data.session?.user) {
          await loadUserProfile(data.session.user.id, data.session.user.email || "");
        } else {
          // If in demo mode without cloud Supabase login, default to Admin synthetic profile for immediate walkthrough
          const savedDemo = localStorage.getItem("carebridge_demo_account");
          if (savedDemo) {
            const acc = JSON.parse(savedDemo) as DemoAccount;
            const uid = acc.role === "doctor"
              ? "70000000-0000-0000-0000-000000000002"
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
        }
      } catch {
        // Session initialization completed
      } finally {
        setIsLoading(false);
      }
    }
    initSession();
  }, [loadUserProfile, fetchHospitalDetails]);

  const signInWithEmail = async (email: string, pass: string): Promise<boolean> => {
    setIsLoading(true);
    setLoginError(null);
    try {
      let supabaseSuccess = false;
      try {
        const { data, error } = await supabase.auth.signInWithPassword({
          email,
          password: pass,
        });
        if (!error && data.user) {
          await loadUserProfile(data.user.id, data.user.email || email);
          supabaseSuccess = true;
          return true;
        }
      } catch {
        // Fallback to backend auth
      }

      if (!supabaseSuccess) {
        try {
          const res = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password: pass }),
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
            });
            await fetchHospitalDetails();
            return true;
          } else {
            const errData = await res.json().catch(() => ({}));
            setLoginError(errData.detail || "Invalid credentials");
            return false;
          }
        } catch {
          setLoginError("Could not connect to authentication service");
          return false;
        }
      }
      return false;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Authentication error";
      setLoginError(msg);
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  const selectDemoAccount = async (account: DemoAccount, pass?: string): Promise<boolean> => {
    setIsLoading(true);
    setLoginError(null);
    try {
      if (pass) {
        const success = await signInWithEmail(account.email, pass);
        if (success) {
          localStorage.setItem("carebridge_demo_account", JSON.stringify(account));
          return true;
        }
      }
      // Demo simulation switch
      const uid = account.role === "doctor"
        ? "70000000-0000-0000-0000-000000000002"
        : account.role === "nurse"
        ? "11111111-0003-0000-0000-000000000032"
        : account.role === "lab_technician"
        ? "11111111-0003-0000-0000-000000000030"
        : account.role === "patient"
        ? "70000000-0000-0000-0000-000000000004"
        : "70000000-0000-0000-0000-000000000001";

      setUser({
        id: uid,
        hospital_id: "11111111-1111-1111-1111-111111111111",
        role: account.role,
        full_name: account.label,
        email: account.email,
      });
      localStorage.setItem("carebridge_demo_account", JSON.stringify(account));
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
      localStorage.removeItem("carebridge_demo_account");
      setActiveDemoToken(null);
      setUser(null);
      setHospital(null);
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

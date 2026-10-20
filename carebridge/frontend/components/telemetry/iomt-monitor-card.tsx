"use client";

import * as React from "react";
import { apiFetch, ProblemDetailsError } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { ShieldCheck, ShieldAlert, AlertTriangle, RefreshCw, Cpu, Zap, Radio } from "lucide-react";

interface ChannelAttribution {
  channel_name: string;
  divergence_score: number;
  relative_divergence_pct: number;
  divergence_status: string;
  clinical_significance: string;
}

interface VerificationResult {
  hospital_id: string;
  patient_id: string;
  device_id: string;
  detection_status: "baseline_consistent" | "inconsistency_detected";
  display_message: string;
  anomaly_probability: number;
  anomaly_logit: number;
  threshold: number;
  is_anomaly: boolean;
  channel_attributions: ChannelAttribution[];
  disclaimer: string;
  inference_latency_ms: number;
  model_version: string;
  automated_task_created: boolean;
  care_task_id?: string;
  created_at: string;
}

interface TelemetryPoint {
  timestamp: string;
  values: Record<string, number>;
}

interface StreamResponse {
  readings?: TelemetryPoint[];
  verification?: VerificationResult;
}

interface SimulateAttackResponse {
  perturbed_readings?: TelemetryPoint[];
  verification_result?: VerificationResult;
}

interface IoMTMonitorCardProps {
  patientId: string;
  patientName?: string;
  deviceId?: string;
}

export function IoMTMonitorCard({
  patientId,
  patientName = "Selected Patient",
  deviceId = "iomt-bedside-node-01",
}: IoMTMonitorCardProps) {
  const [loading, setLoading] = React.useState(false);
  const [simulating, setSimulating] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [readings, setReadings] = React.useState<TelemetryPoint[]>([]);
  const [verification, setVerification] = React.useState<VerificationResult | null>(null);
  const [activeScenario, setActiveScenario] = React.useState<string>("baseline");

  const fetchStream = React.useCallback(async () => {
    if (!patientId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<StreamResponse>(`/api/v1/cscm/stream?patient_id=${patientId}&device_id=${deviceId}`);
      setReadings(data?.readings || []);
      setVerification(data?.verification || null);
      setActiveScenario("baseline");
    } catch (err: unknown) {
      const msg = err instanceof ProblemDetailsError ? err.detail : err instanceof Error ? err.message : "Failed to load IoMT telemetry stream.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [patientId, deviceId]);

  React.useEffect(() => {
    let isSubscribed = true;
    if (!patientId) return;

    Promise.resolve().then(() => {
      if (isSubscribed) {
        setLoading(true);
        setError(null);
      }
    });

    apiFetch<StreamResponse>(`/api/v1/cscm/stream?patient_id=${patientId}&device_id=${deviceId}`)
      .then((data) => {
        if (!isSubscribed) return;
        setReadings(data?.readings || []);
        setVerification(data?.verification || null);
        setActiveScenario("baseline");
      })
      .catch((err: unknown) => {
        if (!isSubscribed) return;
        const msg = err instanceof ProblemDetailsError ? err.detail : err instanceof Error ? err.message : "Failed to load IoMT telemetry stream.";
        setError(msg);
      })
      .finally(() => {
        if (isSubscribed) setLoading(false);
      });

    return () => {
      isSubscribed = false;
    };
  }, [patientId, deviceId]);

  const handleSimulateAttack = async (attackType: string, intensity: number = 1.35) => {
    setSimulating(true);
    setError(null);
    try {
      const res = await apiFetch<SimulateAttackResponse>("/api/v1/cscm/simulate-attack", {
        method: "POST",
        body: JSON.stringify({
          patient_id: patientId,
          device_id: deviceId,
          attack_type: attackType,
          intensity,
        }),
      });
      setReadings(res?.perturbed_readings || []);
      setVerification(res?.verification_result || null);
      setActiveScenario(attackType);
    } catch (err: unknown) {
      const msg = err instanceof ProblemDetailsError ? err.detail : err instanceof Error ? err.message : "Attack simulation failed.";
      setError(msg);
    } finally {
      setSimulating(false);
    }
  };

  const latestReading = readings.length > 0 ? readings[readings.length - 1].values : null;

  return (
    <Card className="border border-slate-200 shadow-sm dark:border-slate-800">
      <CardHeader className="pb-3 border-b border-slate-100 dark:border-slate-800">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center space-x-2">
            <Radio className="w-5 h-5 text-indigo-600 animate-pulse" />
            <div>
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                Bedside IoMT Multi-Channel Monitor
                <Badge variant="outline" className="text-xs bg-indigo-50 text-indigo-700 border-indigo-200">
                  CSCM Model C
                </Badge>
              </CardTitle>
              <CardDescription className="text-xs">
                Device: <code className="font-mono">{deviceId}</code> · Patient: {patientName}
              </CardDescription>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={fetchStream}
              disabled={loading || simulating}
              className="h-8 text-xs"
            >
              <RefreshCw className={`w-3.5 h-3.5 mr-1 ${loading ? "animate-spin" : ""}`} />
              Reset Baseline
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 pt-4">
        {error && (
          <Alert variant="destructive" className="py-2">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle className="text-xs">Telemetry Error</AlertTitle>
            <AlertDescription className="text-xs">{error}</AlertDescription>
          </Alert>
        )}

        {/* 1. Consistency Verification Status Banner */}
        {verification && (
          <div
            className={`p-3 rounded-lg border flex flex-col md:flex-row md:items-center justify-between gap-3 ${
              verification.is_anomaly
                ? "bg-rose-50 border-rose-200 text-rose-950 dark:bg-rose-950/30 dark:border-rose-900"
                : "bg-emerald-50 border-emerald-200 text-emerald-950 dark:bg-emerald-950/30 dark:border-emerald-900"
            }`}
          >
            <div className="flex items-start space-x-3">
              {verification.is_anomaly ? (
                <ShieldAlert className="w-6 h-6 text-rose-600 shrink-0 mt-0.5" />
              ) : (
                <ShieldCheck className="w-6 h-6 text-emerald-600 shrink-0 mt-0.5" />
              )}
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-sm">{verification.display_message}</span>
                  <Badge
                    variant={verification.is_anomaly ? "destructive" : "secondary"}
                    className={`text-xs ${
                      !verification.is_anomaly ? "bg-emerald-100 text-emerald-800 border-emerald-200" : ""
                    }`}
                  >
                    Confidence: {(verification.anomaly_probability * 100).toFixed(1)}%
                  </Badge>
                  {verification.automated_task_created && (
                    <Badge className="bg-amber-500 text-white text-xs">
                      Care Task Created
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
                  CSCM Graph Message Passing · In-process latency:{" "}
                  <strong>{verification.inference_latency_ms.toFixed(1)} ms</strong>
                </p>
              </div>
            </div>

            <div className="text-right text-xs shrink-0">
              <span className="text-slate-500 font-mono text-[11px]">
                Threshold: {(verification.threshold * 100).toFixed(0)}%
              </span>
            </div>
          </div>
        )}

        {/* 2. Physiological Sensor Channels Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <div className="p-3 bg-slate-50 dark:bg-slate-900/50 rounded-lg border border-slate-200 dark:border-slate-800">
            <div className="text-xs text-slate-500 font-medium">Heart Rate</div>
            <div className="text-xl font-bold text-slate-800 dark:text-slate-100">
              {latestReading?.HR ? `${latestReading.HR.toFixed(0)}` : "—"}{" "}
              <span className="text-xs font-normal text-slate-500">bpm</span>
            </div>
          </div>

          <div className="p-3 bg-slate-50 dark:bg-slate-900/50 rounded-lg border border-slate-200 dark:border-slate-800">
            <div className="text-xs text-slate-500 font-medium">Systolic BP (NISys)</div>
            <div className="text-xl font-bold text-slate-800 dark:text-slate-100">
              {latestReading?.NISysABP ? `${latestReading.NISysABP.toFixed(0)}` : "—"}{" "}
              <span className="text-xs font-normal text-slate-500">mmHg</span>
            </div>
          </div>

          <div className="p-3 bg-slate-50 dark:bg-slate-900/50 rounded-lg border border-slate-200 dark:border-slate-800">
            <div className="text-xs text-slate-500 font-medium">Diastolic BP (NIDias)</div>
            <div className="text-xl font-bold text-slate-800 dark:text-slate-100">
              {latestReading?.NIDiasABP ? `${latestReading.NIDiasABP.toFixed(0)}` : "—"}{" "}
              <span className="text-xs font-normal text-slate-500">mmHg</span>
            </div>
          </div>

          <div className="p-3 bg-slate-50 dark:bg-slate-900/50 rounded-lg border border-slate-200 dark:border-slate-800">
            <div className="text-xs text-slate-500 font-medium">Mean Arterial (MAP)</div>
            <div className="text-xl font-bold text-slate-800 dark:text-slate-100">
              {latestReading?.NIMAP ? `${latestReading.NIMAP.toFixed(0)}` : "—"}{" "}
              <span className="text-xs font-normal text-slate-500">mmHg</span>
            </div>
          </div>

          <div className="p-3 bg-slate-50 dark:bg-slate-900/50 rounded-lg border border-slate-200 dark:border-slate-800">
            <div className="text-xs text-slate-500 font-medium">Temperature</div>
            <div className="text-xl font-bold text-slate-800 dark:text-slate-100">
              {latestReading?.Temp ? `${latestReading.Temp.toFixed(1)}` : "—"}{" "}
              <span className="text-xs font-normal text-slate-500">°C</span>
            </div>
          </div>
        </div>

        {/* 3. Grounded Channel Attribution Breakdown */}
        {verification && verification.channel_attributions.length > 0 && (
          <div className="space-y-2 border-t border-slate-100 dark:border-slate-800 pt-3">
            <div className="flex items-center justify-between text-xs text-slate-600 dark:text-slate-400">
              <span className="font-semibold flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5 text-indigo-500" />
                Grounded Channel Divergence Attribution (Physiological Edge Residuals)
              </span>
              <span className="text-[11px] text-slate-500">Relative Discordance %</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {verification.channel_attributions.map((attr) => (
                <div
                  key={attr.channel_name}
                  className={`p-2 rounded border text-xs flex items-center justify-between ${
                    attr.divergence_status === "elevated_graph_divergence"
                      ? "bg-rose-50/60 border-rose-200 dark:bg-rose-950/20"
                      : "bg-slate-50/60 border-slate-200 dark:bg-slate-900/30"
                  }`}
                >
                  <div className="space-y-0.5">
                    <div className="font-semibold flex items-center gap-1.5">
                      <span>{attr.channel_name}</span>
                      {attr.divergence_status === "elevated_graph_divergence" && (
                        <Badge variant="destructive" className="text-[10px] py-0 px-1.5">
                          Elevated Divergence
                        </Badge>
                      )}
                    </div>
                    <div className="text-[11px] text-slate-500 line-clamp-1">
                      {attr.clinical_significance}
                    </div>
                  </div>

                  <div className="text-right shrink-0 ml-2">
                    <div className="font-mono font-bold text-xs">
                      {attr.relative_divergence_pct.toFixed(1)}%
                    </div>
                    <div className="text-[10px] text-slate-400 font-mono">
                      res: {attr.divergence_score.toFixed(2)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 4. Attack Simulation Controls */}
        <div className="space-y-2 border-t border-slate-100 dark:border-slate-800 pt-3">
          <div className="flex items-center justify-between text-xs text-slate-600 dark:text-slate-400">
            <span className="font-semibold flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-amber-500" />
              Live FDIA Attack Demonstration
            </span>
            <span className="text-[11px] text-slate-500">Current mode: {activeScenario}</span>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              variant={activeScenario === "baseline" ? "secondary" : "outline"}
              size="sm"
              onClick={fetchStream}
              disabled={simulating || loading}
              className="text-xs h-8"
            >
              Clean Baseline
            </Button>
            <Button
              variant={activeScenario === "coordinated_scaling" ? "destructive" : "outline"}
              size="sm"
              onClick={() => handleSimulateAttack("coordinated_scaling", 1.4)}
              disabled={simulating || loading}
              className="text-xs h-8"
            >
              Coordinated BP Scaling (+40%)
            </Button>
            <Button
              variant={activeScenario === "coordinated_drift" ? "destructive" : "outline"}
              size="sm"
              onClick={() => handleSimulateAttack("coordinated_drift", 1.2)}
              disabled={simulating || loading}
              className="text-xs h-8"
            >
              Coordinated Drift (+15 mmHg)
            </Button>
            <Button
              variant={activeScenario === "single_channel_drift" ? "destructive" : "outline"}
              size="sm"
              onClick={() => handleSimulateAttack("single_channel_drift", 1.0)}
              disabled={simulating || loading}
              className="text-xs h-8"
            >
              Single Sensor Drift
            </Button>
          </div>
        </div>

        {/* 5. Mandatory Advisory Disclaimer */}
        <div className="p-2.5 bg-amber-50/70 border border-amber-200/80 rounded-md text-[11px] text-amber-900 dark:bg-amber-950/20 dark:border-amber-900 dark:text-amber-300">
          <strong>Advisory Disclaimer:</strong> {verification?.disclaimer || "Advisory integrity warning only. Does not replace clinical assessment or certified biomedical equipment inspection."}
        </div>
      </CardContent>
    </Card>
  );
}

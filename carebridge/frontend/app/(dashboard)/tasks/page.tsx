"use client";

import * as React from "react";
import { useAuth } from "@/lib/auth-context";
import { apiFetch, ProblemDetailsError } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  ClipboardList,
  CheckCircle2,
  AlertCircle,
  Clock,
  UserCheck,
  PlusCircle,
  ShieldAlert,
  AlertTriangle,
} from "lucide-react";

export interface CareTask {
  id: string;
  hospital_id: string;
  patient_id: string;
  encounter_id?: string;
  task_type: string;
  priority: "urgent" | "high" | "routine" | "low";
  status: "pending" | "claimed" | "in_progress" | "completed" | "cancelled";
  title: string;
  description?: string;
  patient_instructions?: string;
  assigned_role: string;
  assigned_to?: string;
  due_date?: string;
  completed_by?: string;
  completed_at?: string;
  completion_notes?: string;
  created_at: string;
  updated_at: string;
}

interface PendingCounts {
  urgent_count: number;
  high_count: number;
  total_pending: number;
  claimed_by_me_count: number;
}

export default function CareTasksPage() {
  const { user } = useAuth();
  const [tasks, setTasks] = React.useState<CareTask[]>([]);
  const [counts, setCounts] = React.useState<PendingCounts>({
    urgent_count: 0,
    high_count: 0,
    total_pending: 0,
    claimed_by_me_count: 0,
  });
  const [loading, setLoading] = React.useState(true);
  const [filterTab, setFilterTab] = React.useState<string>("all");
  const [actionSuccess, setActionSuccess] = React.useState<string | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);

  // Complete Modal
  const [completeModalOpen, setCompleteModalOpen] = React.useState(false);
  const [taskToComplete, setTaskToComplete] = React.useState<CareTask | null>(null);
  const [completionNotes, setCompletionNotes] = React.useState("");
  const [completing, setCompleting] = React.useState(false);

  // Create Modal
  const [createModalOpen, setCreateModalOpen] = React.useState(false);
  const [creating, setCreating] = React.useState(false);
  const [createTitle, setCreateTitle] = React.useState("");
  const [createType, setCreateType] = React.useState("post_op_check");
  const [createPriority, setCreatePriority] = React.useState<"urgent" | "high" | "routine" | "low">("routine");
  const [createRole, setCreateRole] = React.useState("nurse");
  const [createDesc, setCreateDesc] = React.useState("");
  const [createPatientInstructions, setCreatePatientInstructions] = React.useState("");
  const [createPatientId, setCreatePatientId] = React.useState("11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa");

  const [refreshKey, setRefreshKey] = React.useState(0);

  React.useEffect(() => {
    let ignore = false;
    async function load() {
      try {
        const data = await apiFetch<CareTask[]>("/care-tasks");
        if (!ignore && data) setTasks(data);

        const c = await apiFetch<PendingCounts>("/care-tasks/notifications/pending-counts");
        if (!ignore && c) setCounts(c);
      } catch {
        // Fallback
      } finally {
        if (!ignore) setLoading(false);
      }
    }
    load();
    return () => {
      ignore = true;
    };
  }, [refreshKey]);

  const handleClaim = async (task: CareTask) => {
    setActionError(null);
    setActionSuccess(null);
    try {
      await apiFetch(`/care-tasks/${task.id}/claim`, { method: "POST" });
      setActionSuccess(`Task claimed: "${task.title}".`);
      setRefreshKey((k) => k + 1);
    } catch (err: unknown) {
      if (err instanceof ProblemDetailsError) {
        setActionError(err.detail);
      } else {
        setActionError("Failed to claim task.");
      }
    }
  };

  const handleCompleteSubmit = async () => {
    if (!taskToComplete || completionNotes.trim().length < 10) return;
    setCompleting(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      await apiFetch(`/care-tasks/${taskToComplete.id}/complete`, {
        method: "POST",
        body: JSON.stringify({ completion_notes: completionNotes.trim() }),
      });
      setActionSuccess(`Task marked completed with clinical resolution notes recorded.`);
      setCompleteModalOpen(false);
      setCompletionNotes("");
      setTaskToComplete(null);
      setRefreshKey((k) => k + 1);
    } catch (err: unknown) {
      if (err instanceof ProblemDetailsError) {
        setActionError(err.detail);
      } else {
        setActionError("Failed to complete task.");
      }
    } finally {
      setCompleting(false);
    }
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createTitle || !createDesc || !createPatientId) return;
    setCreating(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      await apiFetch("/care-tasks", {
        method: "POST",
        body: JSON.stringify({
          patient_id: createPatientId,
          title: createTitle.trim(),
          task_type: createType,
          priority: createPriority,
          assigned_role: createRole,
          description: createDesc.trim(),
          patient_instructions: createPatientInstructions.trim() || null,
        }),
      });
      setActionSuccess("Care coordination task authored successfully.");
      setCreateModalOpen(false);
      setCreateTitle("");
      setCreateDesc("");
      setCreatePatientInstructions("");
      setRefreshKey((k) => k + 1);
    } catch (err: unknown) {
      if (err instanceof ProblemDetailsError) {
        setActionError(err.detail);
      } else {
        setActionError("Failed to author care task.");
      }
    } finally {
      setCreating(false);
    }
  };

  const filteredTasks = tasks.filter((t) => {
    if (filterTab === "pending") return t.status === "pending";
    if (filterTab === "claimed") return t.assigned_to === user?.id && t.status !== "completed";
    if (filterTab === "urgent") return t.priority === "urgent" || t.priority === "high";
    if (filterTab === "completed") return t.status === "completed";
    return true;
  });

  const getPriorityBadge = (p: string) => {
    if (p === "urgent") {
      return (
        <Badge variant="destructive" className="flex items-center gap-1">
          <ShieldAlert className="h-3 w-3" /> Urgent
        </Badge>
      );
    }
    if (p === "high") {
      return (
        <Badge className="bg-amber-100 text-amber-800 border-amber-300 flex items-center gap-1">
          <AlertTriangle className="h-3 w-3" /> High
        </Badge>
      );
    }
    if (p === "routine") {
      return <Badge variant="outline">Routine</Badge>;
    }
    return <Badge variant="secondary">Low</Badge>;
  };

  const getStatusBadge = (s: string) => {
    if (s === "completed") {
      return (
        <Badge variant="success" className="flex items-center gap-1">
          <CheckCircle2 className="h-3 w-3" /> Completed
        </Badge>
      );
    }
    if (s === "claimed") {
      return (
        <Badge className="bg-blue-100 text-blue-800 border-blue-200 flex items-center gap-1">
          <UserCheck className="h-3 w-3" /> Claimed
        </Badge>
      );
    }
    if (s === "cancelled") {
      return <Badge variant="secondary">Cancelled</Badge>;
    }
    return (
      <Badge variant="warning" className="flex items-center gap-1">
        <Clock className="h-3 w-3" /> Pending
      </Badge>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
            <ClipboardList className="h-6 w-6 text-blue-600" />
            Care Coordination Task Board
          </h1>
          <p className="text-xs text-slate-500">
            Multi-Disciplinary Clinical Tasks, Discharge Follow-Ups & Medication Reviews
          </p>
        </div>
        <Button
          size="md"
          onClick={() => setCreateModalOpen(true)}
          className="flex items-center space-x-1.5 bg-blue-700 hover:bg-blue-800 text-white shrink-0"
        >
          <PlusCircle className="h-4 w-4" />
          <span>New Care Task</span>
        </Button>
      </div>

      {actionSuccess && (
        <Alert variant="success">
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          <AlertTitle>Action Committed</AlertTitle>
          <AlertDescription>{actionSuccess}</AlertDescription>
        </Alert>
      )}

      {actionError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4 text-red-600" />
          <AlertTitle>Notice</AlertTitle>
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      )}

      {/* Metrics Counter Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="bg-red-50/50 border-red-200">
          <CardContent className="p-4">
            <span className="text-[10px] uppercase font-semibold text-red-700">Urgent Tasks</span>
            <div className="text-2xl font-bold text-red-950 mt-1">{counts.urgent_count}</div>
          </CardContent>
        </Card>
        <Card className="bg-amber-50/50 border-amber-200">
          <CardContent className="p-4">
            <span className="text-[10px] uppercase font-semibold text-amber-700">High Priority</span>
            <div className="text-2xl font-bold text-amber-950 mt-1">{counts.high_count}</div>
          </CardContent>
        </Card>
        <Card className="bg-blue-50/50 border-blue-200">
          <CardContent className="p-4">
            <span className="text-[10px] uppercase font-semibold text-blue-700">Open Team Pool</span>
            <div className="text-2xl font-bold text-blue-950 mt-1">{counts.total_pending}</div>
          </CardContent>
        </Card>
        <Card className="bg-slate-50 border-slate-200">
          <CardContent className="p-4">
            <span className="text-[10px] uppercase font-semibold text-slate-600">Claimed By Me</span>
            <div className="text-2xl font-bold text-slate-900 mt-1">{counts.claimed_by_me_count}</div>
          </CardContent>
        </Card>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center space-x-2 border-b border-slate-200 pb-2">
        {[
          { key: "all", label: "All Tasks" },
          { key: "pending", label: "Open Pool" },
          { key: "claimed", label: "Assigned To Me" },
          { key: "urgent", label: "Urgent / High" },
          { key: "completed", label: "Completed" },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setFilterTab(tab.key)}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold capitalize transition-all cursor-pointer ${
              filterTab === tab.key
                ? "bg-blue-700 text-white font-bold"
                : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Task List */}
      <div className="space-y-3">
        {loading ? (
          <div className="p-8 text-center text-xs text-slate-400">Loading care coordination tasks...</div>
        ) : filteredTasks.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-xs text-slate-500">
            No care coordination tasks matching this filter view.
          </div>
        ) : (
          filteredTasks.map((task) => (
            <Card key={task.id} className="hover:border-slate-300 transition-all">
              <CardContent className="p-4">
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                  <div className="space-y-1.5 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      {getPriorityBadge(task.priority)}
                      {getStatusBadge(task.status)}
                      <Badge variant="secondary" className="uppercase font-mono text-[10px]">
                        {task.task_type.replace(/_/g, " ")}
                      </Badge>
                      <span className="text-xs text-slate-500 font-medium">
                        Role: <strong className="text-slate-800 uppercase">{task.assigned_role}</strong>
                      </span>
                    </div>

                    <h3 className="text-sm font-semibold text-slate-900 leading-snug">{task.title}</h3>

                    {task.description && (
                      <p className="text-xs text-slate-600 leading-relaxed">{task.description}</p>
                    )}

                    {task.patient_instructions && (
                      <div className="bg-teal-50 border border-teal-100 rounded-md p-2 mt-2 text-xs text-teal-900">
                        <span className="font-semibold block text-[11px] text-teal-950 uppercase mb-0.5">
                          Patient-Facing Instructions:
                        </span>
                        {task.patient_instructions}
                      </div>
                    )}

                    {task.completion_notes && (
                      <div className="bg-emerald-50 border border-emerald-100 rounded-md p-2 mt-2 text-xs text-emerald-900">
                        <span className="font-semibold block text-[11px] text-emerald-950 uppercase mb-0.5">
                          Resolution Notes:
                        </span>
                        {task.completion_notes}
                      </div>
                    )}

                    {task.due_date && (
                      <div className="text-[11px] text-slate-400 flex items-center gap-1 pt-1">
                        <Clock className="h-3 w-3" /> Due by: {new Date(task.due_date).toLocaleString()}
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex sm:flex-col items-end gap-2 shrink-0">
                    {task.status === "pending" && (
                      <Button
                        size="sm"
                        onClick={() => handleClaim(task)}
                        className="h-8 text-xs bg-blue-700 hover:bg-blue-800 text-white gap-1"
                      >
                        <UserCheck className="h-3.5 w-3.5" /> Claim Task
                      </Button>
                    )}

                    {(task.status === "claimed" || task.status === "in_progress") && (
                      <Button
                        size="sm"
                        onClick={() => {
                          setTaskToComplete(task);
                          setCompletionNotes("");
                          setCompleteModalOpen(true);
                        }}
                        className="h-8 text-xs bg-emerald-600 hover:bg-emerald-700 text-white gap-1"
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" /> Mark Complete
                      </Button>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* Complete Task Dialog */}
      <Dialog open={completeModalOpen} onOpenChange={(val) => !val && setCompleteModalOpen(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Complete Care Task</DialogTitle>
            <DialogDescription>
              Record clinical resolution notes or outreach confirmation. Minimum 10 characters required.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-2">
            <label className="text-xs font-semibold text-slate-700 block">
              Clinical Resolution Notes <span className="text-red-500">*</span>
            </label>
            <textarea
              value={completionNotes}
              onChange={(e) => setCompletionNotes(e.target.value)}
              placeholder="e.g. 'Contacted patient via telephone; confirmed medication tolerance and verified next appointment scheduled for Tuesday.'"
              rows={4}
              className="w-full text-xs p-2.5 rounded-md border border-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-500 text-slate-900"
            />
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setCompleteModalOpen(false)} disabled={completing}>
              Cancel
            </Button>
            <Button
              onClick={handleCompleteSubmit}
              disabled={completing || completionNotes.trim().length < 10}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              {completing ? "Saving..." : "Record & Complete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Task Dialog */}
      <Dialog open={createModalOpen} onOpenChange={(val) => !val && setCreateModalOpen(false)}>
        <DialogContent className="max-w-xl">
          <form onSubmit={handleCreateSubmit}>
            <DialogHeader>
              <DialogTitle>Author Care Coordination Task</DialogTitle>
              <DialogDescription>
                Assign clinical follow-ups, post-op checks, or medication reviews across team roles.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3 py-3 text-xs">
              <div>
                <label className="font-semibold text-slate-700 block mb-1">Task Title *</label>
                <Input
                  required
                  value={createTitle}
                  onChange={(e) => setCreateTitle(e.target.value)}
                  placeholder="e.g. 'Post-Discharge Wound Inspection Follow-Up'"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-slate-700 block mb-1">Task Type</label>
                  <select
                    value={createType}
                    onChange={(e) => setCreateType(e.target.value)}
                    className="w-full h-9 rounded-md border border-slate-300 px-3 bg-white text-xs"
                  >
                    <option value="post_op_check">Post-Op Check</option>
                    <option value="discharge_follow_up">Discharge Follow-Up</option>
                    <option value="medication_reconciliation">Medication Reconciliation</option>
                    <option value="specialist_referral">Specialist Referral</option>
                    <option value="lab_review">Lab Review</option>
                    <option value="patient_outreach">Patient Outreach</option>
                    <option value="caregiver_briefing">Caregiver Briefing</option>
                  </select>
                </div>
                <div>
                  <label className="font-semibold text-slate-700 block mb-1">Priority</label>
                  <select
                    value={createPriority}
                    onChange={(e) => setCreatePriority(e.target.value as "urgent" | "high" | "routine" | "low")}
                    className="w-full h-9 rounded-md border border-slate-300 px-3 bg-white text-xs"
                  >
                    <option value="routine">Routine</option>
                    <option value="high">High</option>
                    <option value="urgent">Urgent</option>
                    <option value="low">Low</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-slate-700 block mb-1">Assigned Role</label>
                  <select
                    value={createRole}
                    onChange={(e) => setCreateRole(e.target.value)}
                    className="w-full h-9 rounded-md border border-slate-300 px-3 bg-white text-xs"
                  >
                    <option value="nurse">Nurse</option>
                    <option value="case_manager">Case Manager</option>
                    <option value="doctor">Doctor</option>
                    <option value="receptionist">Receptionist</option>
                    <option value="any_staff">Any Staff</option>
                  </select>
                </div>
                <div>
                  <label className="font-semibold text-slate-700 block mb-1">Patient MRN / ID</label>
                  <Input
                    required
                    value={createPatientId}
                    onChange={(e) => setCreatePatientId(e.target.value)}
                    placeholder="Patient UUID"
                  />
                </div>
              </div>

              <div>
                <label className="font-semibold text-slate-700 block mb-1">Internal Description *</label>
                <textarea
                  required
                  rows={3}
                  value={createDesc}
                  onChange={(e) => setCreateDesc(e.target.value)}
                  placeholder="Clinical protocol context, relevant vital parameters, and checklist items..."
                  className="w-full text-xs p-2.5 rounded-md border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 text-slate-900"
                />
              </div>

              <div>
                <label className="font-semibold text-slate-700 block mb-1">
                  Patient-Facing Instructions (Optional)
                </label>
                <textarea
                  rows={2}
                  value={createPatientInstructions}
                  onChange={(e) => setCreatePatientInstructions(e.target.value)}
                  placeholder="Patient-friendly next step shown on patient portal (leave blank if internal staff only)..."
                  className="w-full text-xs p-2.5 rounded-md border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 text-slate-900"
                />
              </div>
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setCreateModalOpen(false)} disabled={creating}>
                Cancel
              </Button>
              <Button type="submit" disabled={creating} className="bg-blue-700 hover:bg-blue-800 text-white">
                {creating ? "Authoring..." : "Create Care Task"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

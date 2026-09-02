import React, { useState, useEffect, useRef } from 'react';
import {
  Layers, Play, CheckCircle, AlertCircle, Clock, Server,
  Cpu, Terminal, Trash2, XCircle, Plus, ShieldCheck, Sparkles,
  RefreshCw, Bot
} from 'lucide-react';

interface TemplateCreateRequest {
  ssh_host: string;
  ssh_port: number;
  ssh_username: string;
  ssh_password?: string;
  cloudstack_username: string;
  hypervisor_type: string;
}

interface ExecutionStep {
  name: string;
  description?: string;
  command?: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  output?: string;
  error?: string;
  timestamp?: string;
}

interface EnvironmentInfo {
  distribution: string;
  version: string;
  package_manager: string;
  hypervisor: string;
  filesystem_type: string;
  root_partition: string;
}

interface ExecutionLog {
  execution_id: string;
  status: 'in_progress' | 'completed' | 'failed' | 'cancelled';
  created_at: string;
  updated_at: string;
  detected_environment?: EnvironmentInfo;
  execution_steps: ExecutionStep[];
  validation_checks?: Record<string, boolean>;
  error_message?: string;
  next_steps?: string[];
}

export const App: React.FC = () => {
  const [formData, setFormData] = useState<TemplateCreateRequest>({
    ssh_host: '',
    ssh_port: 22,
    ssh_username: 'root',
    ssh_password: '',
    cloudstack_username: 'centos',
    hypervisor_type: 'auto',
  });

  const [executionId, setExecutionId] = useState<string | null>(null);
  const [execution, setExecution] = useState<ExecutionLog | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [currentPhase, setCurrentPhase] = useState<string>('detection');
  const [aiDiagnosis, setAiDiagnosis] = useState<any | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const consoleBottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (consoleBottomRef.current) {
      consoleBottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [execution?.execution_steps]);

  useEffect(() => {
    if (!executionId) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/template/${executionId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'current_state') {
          setExecution(msg.execution);
        } else if (msg.type === 'phase_change') {
          setCurrentPhase(msg.phase);
        } else if (msg.type === 'environment_detected') {
          setExecution((prev) => prev ? { ...prev, detected_environment: msg.environment } : null);
        } else if (msg.type === 'step_update') {
          setExecution((prev) => {
            if (!prev) return null;
            const existingIdx = prev.execution_steps.findIndex(s => s.name === msg.step.name);
            let updatedSteps = [...prev.execution_steps];
            if (existingIdx >= 0) {
              updatedSteps[existingIdx] = msg.step;
            } else {
              updatedSteps.push(msg.step);
            }
            return { ...prev, execution_steps: updatedSteps };
          });

          if (msg.step.status === 'failed') {
            diagnoseFailure(msg.step);
          }
        } else if (msg.type === 'validation_update') {
          setExecution((prev) => prev ? { ...prev, validation_checks: msg.validation } : null);
        } else if (msg.type === 'execution_complete') {
          setExecution((prev) => prev ? {
            ...prev,
            status: msg.status,
            error_message: msg.error,
            next_steps: msg.result?.next_steps || prev.next_steps,
            validation_checks: msg.result?.validation || prev.validation_checks
          } : null);
        }
      } catch (err) {
        console.error('WS Parse Error:', err);
      }
    };

    return () => {
      ws.close();
    };
  }, [executionId]);

  const diagnoseFailure = async (failedStep: ExecutionStep) => {
    try {
      const res = await fetch('/api/ai/diagnose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          execution_id: executionId,
          step_name: failedStep.name,
          command: failedStep.command || '',
          error_output: failedStep.error || ''
        })
      });
      if (res.ok) {
        const data = await res.json();
        setAiDiagnosis(data);
      }
    } catch (e) {
      console.error('AI diagnosis error:', e);
    }
  };

  const handleStartPipeline = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setAiDiagnosis(null);

    try {
      const res = await fetch('/api/template/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to start pipeline');
      }

      const data = await res.json();
      setExecutionId(data.execution_id);
      setExecution({
        execution_id: data.execution_id,
        status: 'in_progress',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        execution_steps: []
      });
    } catch (err: any) {
      alert(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!executionId) return;
    if (!confirm('Cancel template building run?')) return;
    try {
      await fetch(`/api/template/${executionId}/cancel`, { method: 'POST' });
    } catch (e: any) {
      alert(e.message);
    }
  };

  const resetPipeline = () => {
    setExecutionId(null);
    setExecution(null);
    setAiDiagnosis(null);
  };

  const phases = [
    { id: 'detection', label: 'Detection' },
    { id: 'planning', label: 'Planning' },
    { id: 'execution', label: 'Packages' },
    { id: 'configuration', label: 'Cloud-init' },
    { id: 'sealing', label: 'Sealing' },
    { id: 'validation', label: 'Validation' },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-indigo-500 selection:text-white">
      {/* Header */}
      <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center text-white shadow-lg shadow-indigo-500/20">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-lg tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white via-slate-200 to-indigo-300">
                  StackBill Studio
                </span>
                <span className="text-[10px] uppercase font-bold tracking-widest px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                  CloudStack 4.x
                </span>
              </div>
              <p className="text-xs text-slate-400">AI-Powered VM Template Preparation & Orchestration</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-xs font-medium text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-lg">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              Engine Online
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {!executionId ? (
          /* Form View */
          <div className="max-w-3xl mx-auto space-y-8">
            <div className="text-center space-y-3">
              <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-white">
                Create CloudStack <span className="bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400">Golden Template</span>
              </h1>
              <p className="text-sm text-slate-400 max-w-lg mx-auto">
                Turn any active Linux VM into an official CloudStack template with dynamic cloud-init datasources, guest agents, and deep sealing.
              </p>
            </div>

            <form onSubmit={handleStartPipeline} className="p-8 rounded-3xl bg-slate-900/90 border border-slate-800 shadow-2xl space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="md:col-span-2">
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-300 mb-2">
                    Target VM Host / IP <span className="text-indigo-400">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="192.168.1.100 or vm.lab.local"
                    value={formData.ssh_host}
                    onChange={e => setFormData({ ...formData, ssh_host: e.target.value })}
                    className="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 text-white font-mono text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-300 mb-2">
                    SSH Port
                  </label>
                  <input
                    type="number"
                    value={formData.ssh_port}
                    onChange={e => setFormData({ ...formData, ssh_port: parseInt(e.target.value) || 22 })}
                    className="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 text-white font-mono text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-300 mb-2">
                    SSH Username <span className="text-indigo-400">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.ssh_username}
                    onChange={e => setFormData({ ...formData, ssh_username: e.target.value })}
                    className="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 text-white font-mono text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-300 mb-2">
                    SSH Password
                  </label>
                  <input
                    type="password"
                    placeholder="••••••••••••"
                    value={formData.ssh_password}
                    onChange={e => setFormData({ ...formData, ssh_password: e.target.value })}
                    className="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 text-white text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-300 mb-2">
                    CloudStack Default User
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.cloudstack_username}
                    onChange={e => setFormData({ ...formData, cloudstack_username: e.target.value })}
                    className="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 text-white font-mono text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  />
                </div>

                <div className="md:col-span-2">
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-300 mb-2">
                    Hypervisor Target
                  </label>
                  <select
                    value={formData.hypervisor_type}
                    onChange={e => setFormData({ ...formData, hypervisor_type: e.target.value })}
                    className="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 text-white text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  >
                    <option value="auto">Auto-detect Platform Automatically (Recommended)</option>
                    <option value="kvm">KVM / QEMU (qemu-guest-agent)</option>
                    <option value="xen">XenServer / XCP-ng (xe-guest-utilities)</option>
                    <option value="vmware">VMware vSphere (open-vm-tools)</option>
                    <option value="hyperv">Microsoft Hyper-V</option>
                  </select>
                </div>
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-4 rounded-2xl bg-gradient-to-r from-indigo-600 via-indigo-500 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-extrabold tracking-wide shadow-lg shadow-indigo-500/25 flex items-center justify-center gap-3 transition"
              >
                {isLoading ? (
                  <>
                    <RefreshCw className="w-5 h-5 animate-spin" />
                    <span>Connecting & Launching...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-5 h-5 fill-current" />
                    <span>Launch Template Automation Pipeline</span>
                  </>
                )}
              </button>
            </form>
          </div>
        ) : (
          /* Execution Live Dashboard */
          <div className="space-y-6">
            {/* Top Status Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-2xl bg-slate-900/80 border border-slate-800">
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <h2 className="text-2xl font-bold text-white tracking-tight">Template Pipeline In Progress</h2>
                  <span className={`text-xs font-bold uppercase tracking-wider px-3 py-1 rounded-full flex items-center gap-1.5 ${
                    execution?.status === 'completed' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' :
                    execution?.status === 'failed' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                    'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
                  }`}>
                    {execution?.status === 'completed' && <CheckCircle className="w-3.5 h-3.5" />}
                    {execution?.status === 'failed' && <AlertCircle className="w-3.5 h-3.5" />}
                    {execution?.status === 'in_progress' && <Clock className="w-3.5 h-3.5 animate-spin" />}
                    {execution?.status?.toUpperCase() || 'IN PROGRESS'}
                  </span>
                </div>
                <p className="text-sm text-slate-400 flex items-center gap-2">
                  ID: <code className="font-mono text-indigo-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">{executionId}</code>
                  <span className="text-slate-600">•</span>
                  Target: <span className="font-semibold text-slate-300">{formData.ssh_username}@{formData.ssh_host}</span>
                </p>
              </div>

              <div className="flex items-center gap-3">
                {execution?.status === 'in_progress' && (
                  <button onClick={handleCancel} className="px-4 py-2 text-xs font-semibold rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 flex items-center gap-2">
                    <XCircle className="w-4 h-4" /> Cancel
                  </button>
                )}
                <button onClick={resetPipeline} className="px-4 py-2 text-xs font-semibold rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-2">
                  <Plus className="w-4 h-4" /> New Run
                </button>
              </div>
            </div>

            {/* Stepper */}
            <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800/80">
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                {phases.map((p, idx) => (
                  <div
                    key={p.id}
                    className={`p-3 rounded-xl border flex items-center gap-3 ${
                      currentPhase === p.id ? 'border-indigo-500 bg-indigo-950/40 animate-pulse' :
                      'border-slate-800 bg-slate-950/60'
                    }`}
                  >
                    <div className="w-8 h-8 rounded-lg bg-slate-800 text-slate-300 flex items-center justify-center font-bold text-xs">
                      {idx + 1}
                    </div>
                    <div>
                      <p className="text-xs font-bold text-slate-200">{p.label}</p>
                      <p className="text-[10px] text-slate-500">{currentPhase === p.id ? 'Active' : 'Pending'}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Environment Telemetry */}
            {execution?.detected_environment && (
              <div className="p-6 rounded-2xl bg-gradient-to-br from-slate-900/90 to-indigo-950/30 border border-slate-800">
                <h3 className="text-sm font-bold uppercase tracking-wider text-indigo-400 mb-4 flex items-center gap-2">
                  <Cpu className="w-4 h-4" />
                  Target VM Environment Telemetry
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-6 gap-4 text-xs">
                  <div className="bg-slate-950/70 p-3 rounded-xl border border-slate-800">
                    <span className="text-slate-500 block">Distribution</span>
                    <span className="font-bold text-white uppercase mt-0.5 block">{execution.detected_environment.distribution}</span>
                  </div>
                  <div className="bg-slate-950/70 p-3 rounded-xl border border-slate-800">
                    <span className="text-slate-500 block">Version</span>
                    <span className="font-bold text-white mt-0.5 block">{execution.detected_environment.version}</span>
                  </div>
                  <div className="bg-slate-950/70 p-3 rounded-xl border border-slate-800">
                    <span className="text-slate-500 block">Hypervisor</span>
                    <span className="font-bold text-indigo-400 uppercase mt-0.5 block">{execution.detected_environment.hypervisor}</span>
                  </div>
                  <div className="bg-slate-950/70 p-3 rounded-xl border border-slate-800">
                    <span className="text-slate-500 block">Package Mgr</span>
                    <span className="font-bold text-white font-mono mt-0.5 block">{execution.detected_environment.package_manager}</span>
                  </div>
                  <div className="bg-slate-950/70 p-3 rounded-xl border border-slate-800">
                    <span className="text-slate-500 block">Filesystem</span>
                    <span className="font-bold text-emerald-400 uppercase mt-0.5 block">{execution.detected_environment.filesystem_type}</span>
                  </div>
                  <div className="bg-slate-950/70 p-3 rounded-xl border border-slate-800">
                    <span className="text-slate-500 block">Root Partition</span>
                    <span className="font-bold text-white font-mono text-[11px] mt-0.5 block truncate">{execution.detected_environment.root_partition}</span>
                  </div>
                </div>
              </div>
            )}

            {/* Console & Validation */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Console Stream */}
              <div className="lg:col-span-2 rounded-2xl bg-slate-900/80 border border-slate-800 overflow-hidden flex flex-col h-[520px]">
                <div className="px-4 py-3 bg-slate-950 border-b border-slate-800 flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs font-mono text-slate-400 font-semibold">
                    <Terminal className="w-3.5 h-3.5 text-indigo-400" />
                    telemetry_live.log
                  </div>
                </div>
                <div className="p-4 font-mono text-xs leading-relaxed space-y-2 overflow-y-auto flex-1 terminal-scroll bg-slate-950 text-slate-300">
                  {execution?.execution_steps.map((step, i) => (
                    <div key={i} className="space-y-1">
                      <div className={`flex items-center gap-2 font-semibold ${
                        step.status === 'completed' ? 'text-emerald-400' :
                        step.status === 'failed' ? 'text-red-400' : 'text-indigo-300'
                      }`}>
                        <span>• [{step.status.toUpperCase()}]</span>
                        <span>{step.name}</span>
                      </div>
                      {step.output && (
                        <div className="text-slate-400 pl-4 border-l border-slate-800 text-[11px] whitespace-pre-wrap">
                          {step.output}
                        </div>
                      )}
                      {step.error && (
                        <div className="text-red-400 pl-4 border-l border-red-900 text-[11px] whitespace-pre-wrap">
                          {step.error}
                        </div>
                      )}
                    </div>
                  ))}
                  <div ref={consoleBottomRef} />
                </div>
              </div>

              {/* Validation & Steps */}
              <div className="space-y-6">
                <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800">
                  <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-indigo-400" />
                    Validation Matrix
                  </h3>
                  <div className="space-y-3 text-xs">
                    {execution?.validation_checks ? (
                      Object.entries(execution.validation_checks).map(([key, passed]) => (
                        <div key={key} className="flex items-center justify-between p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                          <span className="text-slate-300">{key}</span>
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                            passed ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                          }`}>
                            {passed ? 'PASSED ✓' : 'FAILED ✗'}
                          </span>
                        </div>
                      ))
                    ) : (
                      <p className="text-slate-500 italic">Awaiting validation phase...</p>
                    )}
                  </div>
                </div>

                {/* AI Diagnostic Card */}
                {aiDiagnosis && (
                  <div className="p-5 rounded-2xl bg-red-950/40 border border-red-800/60 text-xs">
                    <h4 className="font-bold text-red-300 flex items-center gap-1.5 mb-2">
                      <Bot className="w-4 h-4 text-red-400" /> AI Advisor Diagnostics
                    </h4>
                    <p className="text-slate-200 mb-2 font-medium">{aiDiagnosis.root_cause}</p>
                    {aiDiagnosis.remediation_commands?.length > 0 && (
                      <div className="p-2 bg-slate-950 rounded border border-red-900 font-mono text-[11px] text-amber-300 space-y-1 mb-2">
                        {aiDiagnosis.remediation_commands.map((cmd: string, idx: number) => (
                          <div key={idx}>{cmd}</div>
                        ))}
                      </div>
                    )}
                    <p className="text-slate-400 italic">{aiDiagnosis.advice}</p>
                  </div>
                )}

                {/* Next Steps */}
                {execution?.status === 'completed' && execution.next_steps && (
                  <div className="p-6 rounded-2xl bg-emerald-950/40 border border-emerald-800/60">
                    <h3 className="text-sm font-bold text-emerald-400 mb-3 flex items-center gap-2">
                      <Sparkles className="w-4 h-4" /> Ready for CloudStack Template Creation!
                    </h3>
                    <ol className="space-y-2 text-xs text-slate-300 list-decimal list-inside leading-relaxed">
                      {execution.next_steps.map((st, i) => (
                        <li key={i}>{st}</li>
                      ))}
                    </ol>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default App;

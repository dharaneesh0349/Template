/**
 * CloudStack Template Automation - React Frontend
 * Provides UI for template creation with real-time status updates
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { AlertCircle, CheckCircle, Clock, Zap, Server } from 'lucide-react';

// ==================== TYPES ====================

interface TemplateCreateRequest {
  ssh_host: string;
  ssh_port: number;
  ssh_username: string;
  ssh_password: string;
  cloudstack_username: string;
  hypervisor_type: 'auto' | 'kvm' | 'xen' | 'vmware' | 'hyperv';
}

interface ExecutionStep {
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  output?: string;
  error?: string;
  timestamp: string;
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
  status: 'in_progress' | 'completed' | 'failed';
  created_at: string;
  updated_at: string;
  detected_environment?: EnvironmentInfo;
  execution_steps: ExecutionStep[];
  validation_checks?: Record<string, boolean>;
  error_message?: string;
}

// ==================== FORM COMPONENT ====================

export const TemplateCreateForm: React.FC<{
  onSubmit: (request: TemplateCreateRequest) => Promise<void>;
  isLoading: boolean;
}> = ({ onSubmit, isLoading }) => {
  const [formData, setFormData] = useState<TemplateCreateRequest>({
    ssh_host: '',
    ssh_port: 22,
    ssh_username: 'root',
    ssh_password: '',
    cloudstack_username: 'centos',
    hypervisor_type: 'auto',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSubmit(formData);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: name === 'ssh_port' ? parseInt(value) : value
    }));
  };

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl bg-white rounded-lg shadow-md p-8">
      <h2 className="text-2xl font-bold mb-6">Create CloudStack Template</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* SSH Host */}
        <div className="col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            SSH Host/IP Address *
          </label>
          <input
            type="text"
            name="ssh_host"
            value={formData.ssh_host}
            onChange={handleChange}
            placeholder="192.168.1.100"
            required
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        {/* SSH Port */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            SSH Port
          </label>
          <input
            type="number"
            name="ssh_port"
            value={formData.ssh_port}
            onChange={handleChange}
            min="1"
            max="65535"
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        {/* SSH Username */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            SSH Username *
          </label>
          <input
            type="text"
            name="ssh_username"
            value={formData.ssh_username}
            onChange={handleChange}
            required
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        {/* SSH Password */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            SSH Password *
          </label>
          <input
            type="password"
            name="ssh_password"
            value={formData.ssh_password}
            onChange={handleChange}
            required
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        {/* CloudStack Username */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            CloudStack Default User
          </label>
          <input
            type="text"
            name="cloudstack_username"
            value={formData.cloudstack_username}
            onChange={handleChange}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        {/* Hypervisor Type */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Hypervisor Type
          </label>
          <select
            name="hypervisor_type"
            value={formData.hypervisor_type}
            onChange={handleChange}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="auto">Auto-detect (Recommended)</option>
            <option value="kvm">KVM/QEMU</option>
            <option value="xen">Xen Server</option>
            <option value="vmware">VMware</option>
            <option value="hyperv">Hyper-V</option>
          </select>
        </div>
      </div>

      <button
        type="submit"
        disabled={isLoading}
        className="mt-8 w-full bg-blue-600 text-white font-semibold py-2 px-4 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
      >
        {isLoading ? 'Creating Template...' : 'Create Template'}
      </button>
    </form>
  );
};

// ==================== EXECUTION MONITOR COMPONENT ====================

export const ExecutionMonitor: React.FC<{
  execution: ExecutionLog;
}> = ({ execution }) => {
  const stepsContainerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to latest step
  useEffect(() => {
    if (stepsContainerRef.current) {
      stepsContainerRef.current.scrollTop = stepsContainerRef.current.scrollHeight;
    }
  }, [execution.execution_steps]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'running':
        return <Clock className="w-5 h-5 text-blue-500 animate-spin" />;
      case 'failed':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      default:
        return <Clock className="w-5 h-5 text-gray-400" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-50 border-green-200';
      case 'in_progress':
        return 'bg-blue-50 border-blue-200';
      case 'failed':
        return 'bg-red-50 border-red-200';
      default:
        return 'bg-gray-50 border-gray-200';
    }
  };

  return (
    <div className={`w-full max-w-4xl rounded-lg shadow-md p-8 border ${getStatusColor(execution.status)}`}>
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold">Execution Status</h2>
          <span className={`px-3 py-1 rounded-full text-sm font-semibold ${
            execution.status === 'completed' ? 'bg-green-200 text-green-800' :
            execution.status === 'failed' ? 'bg-red-200 text-red-800' :
            'bg-blue-200 text-blue-800'
          }`}>
            {execution.status.toUpperCase()}
          </span>
        </div>
        <p className="text-sm text-gray-600">
          Execution ID: <code className="bg-gray-100 px-2 py-1 rounded">{execution.execution_id}</code>
        </p>
      </div>

      {/* Environment Detection */}
      {execution.detected_environment && (
        <div className="mb-6 p-4 bg-white rounded-lg border border-gray-200">
          <h3 className="font-semibold text-lg mb-3 flex items-center gap-2">
            <Server className="w-5 h-5" />
            Detected Environment
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-gray-600">Distribution</span>
              <p className="font-semibold">{execution.detected_environment.distribution} {execution.detected_environment.version}</p>
            </div>
            <div>
              <span className="text-gray-600">Hypervisor</span>
              <p className="font-semibold">{execution.detected_environment.hypervisor}</p>
            </div>
            <div>
              <span className="text-gray-600">Package Manager</span>
              <p className="font-semibold">{execution.detected_environment.package_manager}</p>
            </div>
            <div>
              <span className="text-gray-600">Filesystem</span>
              <p className="font-semibold">{execution.detected_environment.filesystem_type}</p>
            </div>
            <div>
              <span className="text-gray-600">Root Partition</span>
              <p className="font-semibold">{execution.detected_environment.root_partition}</p>
            </div>
          </div>
        </div>
      )}

      {/* Execution Steps */}
      <div className="mb-6">
        <h3 className="font-semibold text-lg mb-3">Execution Steps</h3>
        <div
          ref={stepsContainerRef}
          className="space-y-2 bg-white rounded-lg border border-gray-200 p-4 max-h-96 overflow-y-auto"
        >
          {execution.execution_steps.length === 0 ? (
            <p className="text-gray-500 text-center py-8">Waiting for execution to start...</p>
          ) : (
            execution.execution_steps.map((step, index) => (
              <div
                key={index}
                className="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50 transition-colors"
              >
                {getStatusIcon(step.status)}
                <div className="flex-1">
                  <p className="font-semibold text-sm">{step.name}</p>
                  {step.output && (
                    <p className="text-xs text-gray-600 mt-1 whitespace-nowrap overflow-hidden text-ellipsis">
                      {step.output}
                    </p>
                  )}
                  {step.error && (
                    <p className="text-xs text-red-600 mt-1">{step.error}</p>
                  )}
                </div>
                <span className="text-xs text-gray-500">
                  {new Date(step.timestamp).toLocaleTimeString()}
                </span>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Error Message */}
      {execution.error_message && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
          <h3 className="font-semibold text-red-800 mb-2 flex items-center gap-2">
            <AlertCircle className="w-5 h-5" />
            Error
          </h3>
          <p className="text-sm text-red-700">{execution.error_message}</p>
        </div>
      )}

      {/* Validation Checks */}
      {execution.validation_checks && (
        <div className="mb-6 p-4 bg-white rounded-lg border border-gray-200">
          <h3 className="font-semibold text-lg mb-3 flex items-center gap-2">
            <Zap className="w-5 h-5" />
            Validation Checks
          </h3>
          <div className="space-y-2">
            {Object.entries(execution.validation_checks).map(([check, passed]) => (
              <div key={check} className="flex items-center gap-2 text-sm">
                {passed ? (
                  <CheckCircle className="w-4 h-4 text-green-500" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-red-500" />
                )}
                <span className={passed ? 'text-green-700' : 'text-red-700'}>
                  {check}: {passed ? 'PASSED' : 'FAILED'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Next Steps */}
      {execution.status === 'completed' && (
        <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
          <h3 className="font-semibold text-green-800 mb-3">✅ Deployment Completed</h3>
          <ol className="space-y-2 text-sm text-green-700 list-decimal list-inside">
            <li>SSH disconnect from the VM</li>
            <li>Shutdown VM in CloudStack UI</li>
            <li>Navigate to: Compute &gt; Volumes</li>
            <li>Select the root volume</li>
            <li>Create Template from Volume</li>
            <li>Template will be ready for deployment</li>
          </ol>
        </div>
      )}
    </div>
  );
};

// ==================== MAIN APP COMPONENT ====================

export const TemplateAutomationApp: React.FC = () => {
  const [executionId, setExecutionId] = useState<string | null>(null);
  const [execution, setExecution] = useState<ExecutionLog | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Setup WebSocket connection for real-time updates
  useEffect(() => {
    if (!executionId) return;

    const connectWebSocket = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/template/${executionId}`;
      
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        console.log('WebSocket connected');
        // Send ping every 30 seconds to keep connection alive
        setInterval(() => {
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send('ping');
          }
        }, 30000);
      };

      wsRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);

          switch (message.type) {
            case 'current_state':
              setExecution(message.execution);
              break;
            case 'step_update':
              setExecution(prev => {
                if (!prev) return null;
                return {
                  ...prev,
                  execution_steps: [...prev.execution_steps, message.step]
                };
              });
              break;
            case 'environment_detected':
              setExecution(prev => {
                if (!prev) return null;
                return {
                  ...prev,
                  detected_environment: message.environment
                };
              });
              break;
            case 'execution_complete':
              setExecution(prev => {
                if (!prev) return null;
                return {
                  ...prev,
                  status: message.status
                };
              });
              setIsLoading(false);
              break;
          }
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };

      wsRef.current.onerror = (event) => {
        console.error('WebSocket error:', event);
      };

      wsRef.current.onclose = () => {
        console.log('WebSocket disconnected');
      };
    };

    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [executionId]);

  const handleSubmit = async (request: TemplateCreateRequest) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/template/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request)
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const data = await response.json();
      setExecutionId(data.execution_id);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            CloudStack Template Automation
          </h1>
          <p className="text-lg text-gray-600">
            AI-driven, dynamic template creation
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-8 p-4 bg-red-50 border border-red-200 rounded-lg flex gap-3">
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-red-800">Error</h3>
              <p className="text-sm text-red-700">{error}</p>
            </div>
          </div>
        )}

        {/* Main Content */}
        {!executionId ? (
          <TemplateCreateForm
            onSubmit={handleSubmit}
            isLoading={isLoading}
          />
        ) : (
          execution && <ExecutionMonitor execution={execution} />
        )}

        {/* Footer */}
        <div className="mt-12 text-center text-sm text-gray-600">
          <p>
            🔐 Your SSH credentials are transmitted securely and never stored.
          </p>
        </div>
      </div>
    </div>
  );
};

export default TemplateAutomationApp;

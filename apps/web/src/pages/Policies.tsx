import React, { useEffect, useState } from 'react';
import { Plus, FileJson, Layers, Cpu, Code2, Play } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { apiFetch } from '../lib/api';

interface Policy {
  id: string;
  name: string;
  description: string;
  framework: string;
  severity: string;
  enabled: boolean;
}

const Policies = () => {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [isCreating, setIsCreating] = useState(false);
  const [newPolicy, setNewPolicy] = useState({
    name: '',
    description: '',
    framework: 'Base Security',
    policy_language: 'cedar',
    policy_content: '',
    severity: 'medium'
  });
  const [isGenerating, setIsGenerating] = useState(false);
  const [aiExplanation, setAiExplanation] = useState('');

  useEffect(() => {
    fetchPolicies();
  }, []);

  const fetchPolicies = async () => {
    try {
      const res = await apiFetch('/v1/policies');
      if (res.ok) {
        const data = await res.json();
        setPolicies(data);
      }
    } catch (e) {
      console.error("Failed to fetch policies:", e);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await apiFetch('/v1/policies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newPolicy)
      });
      if (res.ok) {
        setIsCreating(false);
        fetchPolicies();
        setNewPolicy({ ...newPolicy, name: '', description: '', policy_content: '' });
      }
    } catch (e) {
      console.error("Failed to create policy:", e);
    }
  };

  return (
    <div className="space-y-8 pb-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white/90">Policy Engine</h1>
          <p className="text-sm text-white/50 mt-1">Deterministic guardrails parsed natively by the OS kernel.</p>
        </div>
        <button 
          onClick={() => setIsCreating(true)}
          className="bg-primary/20 hover:bg-primary/30 border border-primary/50 text-primary-foreground px-5 py-2.5 rounded-lg font-medium text-sm flex items-center transition-all shadow-[0_0_15px_rgba(59,130,246,0.2)] hover:shadow-[0_0_25px_rgba(59,130,246,0.4)]"
        >
          <Plus className="w-4 h-4 mr-2" />
          Deploy New Rule
        </button>
      </div>

      <AnimatePresence>
        {isCreating && (
          <motion.div 
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="bg-black/40 border border-primary/20 rounded-2xl p-8 shadow-[0_0_30px_rgba(0,0,0,0.5)] backdrop-blur-xl relative">
              <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent" />
              
              <div className="flex items-center space-x-3 mb-6">
                <div className="p-2 bg-primary/10 rounded-lg border border-primary/20">
                  <Cpu className="w-5 h-5 text-primary" />
                </div>
                <h2 className="text-xl font-semibold text-white/90">Rule Builder</h2>
              </div>

              <form onSubmit={handleCreate} className="space-y-6 max-w-4xl">
                <div className="grid grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <label className="text-xs font-semibold text-white/50 tracking-wider uppercase">Rule Identifier</label>
                    <input 
                      type="text" required
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-sm text-white/90 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/50 transition-all placeholder:text-white/20"
                      value={newPolicy.name}
                      onChange={e => setNewPolicy({...newPolicy, name: e.target.value})}
                      placeholder="e.g. block_large_refunds"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs font-semibold text-white/50 tracking-wider uppercase">Compliance Framework</label>
                    <div className="relative">
                      <select 
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-sm text-white/90 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/50 transition-all appearance-none"
                        value={newPolicy.framework}
                        onChange={e => setNewPolicy({...newPolicy, framework: e.target.value})}
                      >
                        <option className="bg-gray-900">Base Security</option>
                        <option className="bg-gray-900">HIPAA</option>
                        <option className="bg-gray-900">SOX</option>
                        <option className="bg-gray-900">PCI-DSS</option>
                      </select>
                      <Layers className="w-4 h-4 text-white/40 absolute right-4 top-3.5 pointer-events-none" />
                    </div>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <label className="text-xs font-semibold text-white/50 tracking-wider uppercase">Intent Description</label>
                    <button
                      type="button"
                      disabled={isGenerating || !newPolicy.description}
                      onClick={async () => {
                        setIsGenerating(true);
                        setAiExplanation('');
                        try {
                          const res = await apiFetch('/v1/policies/generate', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ natural_language: newPolicy.description })
                          });
                          if (res.ok) {
                            const data = await res.json();
                            setNewPolicy(prev => ({
                              ...prev,
                              policy_content: data.cedar_content,
                              policy_language: 'cedar'
                            }));
                            setAiExplanation(data.explanation);
                          } else {
                            const errorData = await res.json();
                            setAiExplanation(`⚠️ Error: ${errorData.detail || 'Failed to translate'}`);
                          }
                        } catch (err) {
                          setAiExplanation('⚠️ Connection failure. Is FastAPI running?');
                        } finally {
                          setIsGenerating(false);
                        }
                      }}
                      className="text-xs font-semibold text-primary-foreground bg-primary/20 hover:bg-primary/30 border border-primary/50 rounded px-2.5 py-1 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      {isGenerating ? '🪄 Translating...' : '🪄 Translate to Cedar'}
                    </button>
                  </div>
                  <input 
                    type="text" required
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-sm text-white/90 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/50 transition-all placeholder:text-white/20"
                    value={newPolicy.description}
                    onChange={e => setNewPolicy({...newPolicy, description: e.target.value})}
                    placeholder="Describe what this rule prevents in plain English"
                  />
                  {aiExplanation && (
                    <p className="text-xs text-white/70 italic mt-1 bg-white/5 border border-white/5 rounded p-2">
                      {aiExplanation}
                    </p>
                  )}
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between items-end mb-1">
                    <label className="text-xs font-semibold text-white/50 tracking-wider uppercase">Kernel Evaluation Logic (Cedar)</label>
                    <div className="flex items-center text-xs text-primary/70 bg-primary/10 px-2 py-1 rounded font-mono">
                      <Code2 className="w-3 h-3 mr-1" />
                      Cedar AST
                    </div>
                  </div>
                  <textarea 
                    required
                    className="w-full bg-[#0a0a0f] border border-white/10 rounded-lg px-4 py-3 text-sm text-emerald-400/90 font-mono h-40 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/50 transition-all custom-scrollbar placeholder:text-white/10"
                    value={newPolicy.policy_content}
                    onChange={e => setNewPolicy({...newPolicy, policy_content: e.target.value})}
                    placeholder="forbid(principal, action, resource) when { ... };"
                  />
                </div>

                <div className="flex justify-end space-x-4 pt-4 border-t border-white/10">
                  <button 
                    type="button" 
                    onClick={() => setIsCreating(false)}
                    className="px-5 py-2.5 text-sm font-medium border border-white/10 text-white/70 hover:bg-white/5 rounded-lg transition-colors"
                  >
                    Discard
                  </button>
                  <button 
                    type="submit"
                    className="px-5 py-2.5 text-sm font-medium bg-primary/20 border border-primary/50 text-primary-foreground hover:bg-primary/30 rounded-lg flex items-center transition-all shadow-[0_0_15px_rgba(59,130,246,0.2)]"
                  >
                    <Play className="w-4 h-4 mr-2" />
                    Commit to Edge
                  </button>
                </div>
              </form>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="bg-white/5 border border-white/10 rounded-2xl shadow-2xl backdrop-blur-md overflow-hidden relative">
        <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent" />
        <table className="w-full text-left text-sm">
          <thead className="bg-black/40 border-b border-white/10">
            <tr>
              <th className="px-6 py-4 font-semibold text-white/50 uppercase tracking-wider text-xs">Status</th>
              <th className="px-6 py-4 font-semibold text-white/50 uppercase tracking-wider text-xs">Rule Def</th>
              <th className="px-6 py-4 font-semibold text-white/50 uppercase tracking-wider text-xs">Framework</th>
              <th className="px-6 py-4 font-semibold text-white/50 uppercase tracking-wider text-xs">Severity</th>
              <th className="px-6 py-4 font-semibold text-white/50 uppercase tracking-wider text-xs">Config</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {policies.length === 0 && (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center text-white/40">
                  <FileJson className="w-12 h-12 mx-auto mb-3 opacity-20" />
                  <p>No active guardrails. Agents are running in unconstrained mode.</p>
                </td>
              </tr>
            )}
            {policies.map((policy, i) => (
              <motion.tr 
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                key={policy.id} 
                className="hover:bg-white/5 transition-colors group"
              >
                <td className="px-6 py-4">
                  {policy.enabled ? (
                    <div className="flex items-center space-x-2">
                      <span className="relative flex h-2.5 w-2.5">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500"></span>
                      </span>
                      <span className="text-green-400 text-xs font-medium">Active</span>
                    </div>
                  ) : (
                    <div className="flex items-center space-x-2">
                      <span className="h-2.5 w-2.5 rounded-full bg-red-500/50"></span>
                      <span className="text-red-400/50 text-xs font-medium">Disabled</span>
                    </div>
                  )}
                </td>
                <td className="px-6 py-4">
                  <div className="font-medium text-white/90">{policy.name}</div>
                  <div className="text-white/40 text-xs mt-1">{policy.description}</div>
                </td>
                <td className="px-6 py-4">
                  <span className="inline-flex items-center px-2.5 py-1 rounded-md border border-white/10 bg-white/5 text-xs font-medium text-white/70">
                    {policy.framework}
                  </span>
                </td>
                <td className="px-6 py-4 capitalize">
                  <span className={`text-xs font-medium ${
                    policy.severity === 'high' ? 'text-red-400' : 'text-yellow-400'
                  }`}>
                    {policy.severity}
                  </span>
                </td>
                <td className="px-6 py-4">
                  <button className="text-white/30 hover:text-white/90 transition-colors">
                    <FileJson className="w-4 h-4" />
                  </button>
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Policies;

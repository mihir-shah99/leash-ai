import { useEffect, useState, useRef } from 'react';
import { Activity, Shield, ShieldAlert, FileText, XCircle, Terminal, Zap } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { motion, AnimatePresence } from 'framer-motion';
import { apiFetch } from '../lib/api';

interface AuditEvent {
  event_id: string;
  time: string;
  action_type: string;
  action_detail: any;
  decision: string;
  violations: string[];
}

const Dashboard = () => {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const streamRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchEvents();
    const interval = setInterval(fetchEvents, 3000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (streamRef.current) {
      streamRef.current.scrollTop = 0;
    }
  }, [events]);

  const fetchEvents = async () => {
    try {
      const res = await apiFetch('/v1/telemetry');
      if (res.ok) {
        const data = await res.json();
        // Just for visual effect in MVP, we might duplicate some if few
        setEvents(data);
      }
    } catch (e) {
      console.error("Failed to fetch telemetry:", e);
    }
  };

  const totalEvaluated = events.length;
  const blockedActions = events.filter(e => e.decision === 'DENY').length;
  const complianceScore = totalEvaluated > 0 
    ? Math.round(((totalEvaluated - blockedActions) / totalEvaluated) * 100) 
    : 100;

  // Transform data for chart (Dummy time series for visual pop in MVP)
  const chartData = [
    { name: '10:00', allowed: 400, blocked: 24 },
    { name: '10:05', allowed: 300, blocked: 13 },
    { name: '10:10', allowed: 200, blocked: 98 },
    { name: '10:15', allowed: 278, blocked: 39 },
    { name: '10:20', allowed: 189, blocked: 48 },
    { name: '10:25', allowed: 239, blocked: 38 },
    { name: '10:30', allowed: 349, blocked: 43 },
    { name: '10:35', allowed: Math.max(0, totalEvaluated - blockedActions), blocked: blockedActions },
  ];

  return (
    <div className="space-y-8 pb-10">
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {/* Metric Cards */}
        <MetricCard 
          title="Governed Agents" 
          value="1" 
          icon={<Activity className="w-5 h-5 text-blue-400" />} 
          trend="+1 active"
          glowColor="rgba(96, 165, 250, 0.5)"
        />
        <MetricCard 
          title="Total Actions Evaluated" 
          value={totalEvaluated.toLocaleString()} 
          icon={<Shield className="w-5 h-5 text-indigo-400" />} 
          trend="Live"
          glowColor="rgba(129, 140, 248, 0.5)"
        />
        <MetricCard 
          title="Blocked Actions" 
          value={blockedActions.toString()} 
          icon={<ShieldAlert className="w-5 h-5 text-red-500" />} 
          trend={`${blockedActions > 0 ? 'Threats neutralized' : 'Secure'}`}
          glowColor="rgba(239, 68, 68, 0.6)"
          isAlert={blockedActions > 0}
        />
        <MetricCard 
          title="Compliance Score" 
          value={`${complianceScore}%`} 
          icon={<FileText className="w-5 h-5 text-emerald-400" />} 
          trend="Optimal"
          glowColor="rgba(52, 211, 153, 0.5)"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[500px]">
        {/* Main Chart Area */}
        <div className="lg:col-span-2 bg-white/5 border border-white/10 rounded-2xl shadow-2xl backdrop-blur-md flex flex-col overflow-hidden relative">
          <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent" />
          <div className="p-6 border-b border-white/10 flex items-center justify-between bg-black/20">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-primary/10 rounded-lg border border-primary/20">
                <Zap className="w-4 h-4 text-primary" />
              </div>
              <h2 className="font-semibold text-white/90 tracking-wide">Action Volume Matrix</h2>
            </div>
          </div>
          <div className="p-6 flex-1 w-full h-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorAllowed" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorBlocked" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="name" fontSize={11} stroke="rgba(255,255,255,0.4)" tickLine={false} axisLine={false} />
                <YAxis fontSize={11} stroke="rgba(255,255,255,0.4)" tickLine={false} axisLine={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: 'rgba(0,0,0,0.8)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', backdropFilter: 'blur(8px)' }}
                  itemStyle={{ color: '#fff' }}
                />
                <Area type="monotone" dataKey="allowed" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorAllowed)" />
                <Area type="monotone" dataKey="blocked" stroke="#ef4444" strokeWidth={2} fillOpacity={1} fill="url(#colorBlocked)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Live Event Stream */}
        <div className="bg-white/5 border border-white/10 rounded-2xl shadow-2xl backdrop-blur-md flex flex-col overflow-hidden relative">
          <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent" />
          <div className="p-6 border-b border-white/10 flex items-center justify-between bg-black/20">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-white/5 rounded-lg border border-white/10">
                <Terminal className="w-4 h-4 text-white/70" />
              </div>
              <h2 className="font-semibold text-white/90 tracking-wide">Live Intercept Feed</h2>
            </div>
            <div className="flex items-center">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500"></span>
              </span>
            </div>
          </div>
          <div 
            ref={streamRef}
            className="flex-1 overflow-auto p-4 space-y-3 custom-scrollbar"
          >
            <AnimatePresence>
              {events.length === 0 ? (
                <motion.div 
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  className="h-full flex items-center justify-center text-sm text-white/40 font-mono"
                >
                  Listening on OS kernel hooks...
                </motion.div>
              ) : events.map(event => (
                <motion.div 
                  key={event.event_id} 
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  className={`p-4 rounded-xl border backdrop-blur-sm relative overflow-hidden ${
                    event.decision === 'ALLOW' 
                      ? 'bg-blue-900/10 border-blue-500/20'
                      : 'bg-red-900/10 border-red-500/30'
                  }`}
                >
                  {/* Subtle left glow line */}
                  <div className={`absolute left-0 top-0 bottom-0 w-1 ${event.decision === 'ALLOW' ? 'bg-blue-500/50' : 'bg-red-500/80 shadow-[0_0_10px_rgba(239,68,68,0.8)]'}`} />
                  
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-mono text-[10px] text-white/50 tracking-wider">
                      {new Date(event.time).toISOString().split('T')[1].replace('Z', '')}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-widest ${
                      event.decision === 'ALLOW' 
                        ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                        : 'bg-red-500/20 text-red-400 border border-red-500/30 animate-pulse'
                    }`}>
                      {event.decision}
                    </span>
                  </div>
                  <div className="font-mono text-xs text-white/80 mb-2">
                    <span className="text-white/40">$</span> {event.action_type}
                  </div>
                  
                  {/* Action detail payload preview */}
                  <div className="bg-black/40 rounded p-2 border border-white/5 font-mono text-[10px] text-emerald-400/70 overflow-hidden text-ellipsis whitespace-nowrap">
                    {JSON.stringify(event.action_detail)}
                  </div>

                  {event.decision === 'DENY' && event.violations.length > 0 && (
                    <div className="mt-3 text-xs text-red-400 flex items-start bg-red-950/30 p-2 rounded border border-red-900/50">
                      <XCircle className="w-3.5 h-3.5 mr-1.5 mt-0.5 flex-shrink-0" />
                      <span className="font-medium">{event.violations[0]}</span>
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
};

const MetricCard = ({ title, value, icon, trend, glowColor, isAlert = false }: any) => (
  <motion.div 
    whileHover={{ y: -2 }}
    className="bg-white/5 border border-white/10 rounded-2xl p-6 shadow-xl backdrop-blur-md relative overflow-hidden group"
  >
    {/* Ambient Glow */}
    <div 
      className="absolute -right-6 -top-6 w-24 h-24 rounded-full blur-2xl opacity-20 group-hover:opacity-40 transition-opacity duration-500"
      style={{ backgroundColor: glowColor }}
    />
    
    <div className="flex items-center justify-between mb-4 relative z-10">
      <p className="text-xs font-medium text-white/50 tracking-wider uppercase">{title}</p>
      <div className="p-2 bg-white/5 rounded-lg border border-white/10">
        {icon}
      </div>
    </div>
    <div className="relative z-10">
      <p className={`text-3xl font-bold tracking-tight ${isAlert ? 'text-red-400 drop-shadow-[0_0_8px_rgba(239,68,68,0.5)]' : 'text-white/90'}`}>
        {value}
      </p>
      <p className="text-xs text-white/40 mt-2 font-medium">{trend}</p>
    </div>
  </motion.div>
);

export default Dashboard;

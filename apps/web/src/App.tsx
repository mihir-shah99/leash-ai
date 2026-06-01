import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Shield, LayoutDashboard, Activity, FileText, Settings, ShieldAlert, Hexagon } from 'lucide-react';
import React from 'react';
import { motion } from 'framer-motion';
import Dashboard from './pages/Dashboard';
import Policies from './pages/Policies';

const Layout = ({ children }: { children: React.ReactNode }) => {
  const location = useLocation();

  const isActive = (path: string) => location.pathname === path;

  const navItems = [
    { path: '/', icon: LayoutDashboard, label: 'Overview' },
    { path: '/policies', icon: Shield, label: 'Policies' },
    { path: '/audit', icon: Activity, label: 'Audit Vault' },
    { path: '/reports', icon: FileText, label: 'Reports' },
  ];

  return (
    <div className="flex h-screen bg-black text-foreground overflow-hidden selection:bg-primary/30">
      {/* Sidebar with Glassmorphism */}
      <aside className="w-64 border-r border-white/10 bg-black/40 backdrop-blur-xl flex flex-col relative z-20">
        <div className="h-16 flex items-center px-6 border-b border-white/10">
          <Hexagon className="w-6 h-6 text-primary mr-2 fill-primary/20" />
          <span className="font-bold text-lg tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60">
            AgentShield
          </span>
        </div>
        
        <nav className="flex-1 p-4 space-y-2">
          {navItems.map((item) => (
            <Link 
              key={item.path}
              to={item.path} 
              className="relative flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-all group"
            >
              {isActive(item.path) && (
                <motion.div 
                  layoutId="activeNav"
                  className="absolute inset-0 bg-primary/10 rounded-lg border border-primary/20"
                  transition={{ type: "spring", stiffness: 300, damping: 30 }}
                />
              )}
              <item.icon className={`w-4 h-4 mr-3 relative z-10 ${isActive(item.path) ? 'text-primary' : 'text-muted-foreground group-hover:text-foreground transition-colors'}`} />
              <span className={`relative z-10 ${isActive(item.path) ? 'text-primary shadow-primary/20 drop-shadow-md' : 'text-muted-foreground group-hover:text-foreground transition-colors'}`}>
                {item.label}
              </span>
            </Link>
          ))}
        </nav>
        
        <div className="p-4 border-t border-white/10">
          <Link to="/settings" className="flex items-center px-3 py-2 text-sm font-medium rounded-lg text-muted-foreground hover:bg-white/5 hover:text-foreground transition-colors">
            <Settings className="w-4 h-4 mr-3" />
            Settings
          </Link>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col relative z-10">
        {/* Glow effects in background */}
        <div className="absolute top-0 right-0 w-96 h-96 bg-primary/10 rounded-full blur-[120px] -z-10" />
        <div className="absolute bottom-0 left-1/2 w-[500px] h-[500px] bg-blue-900/10 rounded-full blur-[150px] -z-10" />

        <header className="h-16 border-b border-white/10 bg-black/40 backdrop-blur-md flex items-center px-8 justify-between sticky top-0 z-20">
          <h1 className="text-lg font-medium text-white/90 capitalize tracking-wide">
            {location.pathname === '/' ? 'Security Overview' : location.pathname.substring(1)}
          </h1>
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-green-500/10 border border-green-500/20 text-green-400 text-xs font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              <span>System Online</span>
            </div>
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary/40 to-primary/10 border border-primary/30 flex items-center justify-center text-primary font-medium text-xs shadow-[0_0_15px_rgba(59,130,246,0.3)]">
              MS
            </div>
          </div>
        </header>
        
        <div className="flex-1 overflow-auto p-8 custom-scrollbar">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="h-full"
          >
            {children}
          </motion.div>
        </div>
      </main>
    </div>
  );
};

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/policies" element={<Policies />} />
          <Route path="*" element={<div className="flex items-center justify-center h-full text-muted-foreground">Module coming soon...</div>} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}

export default App;

import React from 'react';
import {
  LayoutDashboard,
  Database,
  Cpu,
  Layers,
  Calculator,
  GitCompare,
  FileText,
  Moon,
  Sun,
  WifiOff,
} from 'lucide-react';

export type NavTab = 'dashboard' | 'datasets' | 'training' | 'models' | 'estimate' | 'scenarios' | 'reports';

interface NavbarProps {
  currentTab: NavTab;
  onTabChange: (tab: NavTab) => void;
  currency: string;
  onCurrencyChange: (curr: string) => void;
  isDark: boolean;
  onToggleTheme: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentTab,
  onTabChange,
  currency,
  onCurrencyChange,
  isDark,
  onToggleTheme,
}) => {
  const tabs: Array<{ id: NavTab; label: string; icon: React.ReactNode }> = [
    { id: 'dashboard', label: 'Dashboard', icon: <LayoutDashboard size={18} /> },
    { id: 'datasets', label: 'Datasets', icon: <Database size={18} /> },
    { id: 'training', label: 'Training', icon: <Cpu size={18} /> },
    { id: 'models', label: 'Models', icon: <Layers size={18} /> },
    { id: 'estimate', label: 'Estimate', icon: <Calculator size={18} /> },
    { id: 'scenarios', label: 'Scenarios', icon: <GitCompare size={18} /> },
    { id: 'reports', label: 'Reports', icon: <FileText size={18} /> },
  ];

  return (
    <header
      style={{
        background: 'var(--bg-surface)',
        borderBottom: '1px solid var(--border)',
        position: 'sticky',
        top: 0,
        zIndex: 100,
      }}
    >
      <div
        style={{
          maxWidth: '1400px',
          margin: '0 auto',
          padding: '0 20px',
          height: '64px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '8px',
              background: 'var(--primary)',
              color: '#fff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 700,
              fontSize: '1.1rem',
            }}
          >
            E3
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: '1rem', letterSpacing: '-0.02em' }}>
              ESTIMO 3.0
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
              Cost & Effort Engine
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav
          role="navigation"
          aria-label="Main Navigation"
          style={{ display: 'flex', gap: '4px', overflowX: 'auto' }}
        >
          {tabs.map((tab) => {
            const isActive = currentTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
                aria-current={isActive ? 'page' : undefined}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '8px 14px',
                  border: 'none',
                  background: isActive ? 'var(--primary-light)' : 'transparent',
                  color: isActive ? 'var(--primary)' : 'var(--text-secondary)',
                  fontWeight: isActive ? 600 : 500,
                  fontSize: '0.875rem',
                  borderRadius: 'var(--radius-sm)',
                }}
              >
                {tab.icon}
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Settings, Currency & Status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Offline indicator */}
          <div
            title="Application operates entirely local and offline"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              fontSize: '0.75rem',
              color: 'var(--text-muted)',
              padding: '4px 8px',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--bg-surface-elevated)',
            }}
          >
            <WifiOff size={14} />
            <span>Offline Capable</span>
          </div>

          {/* Currency selector (Rule R7: default INR, configurable) */}
          <select
            value={currency}
            onChange={(e) => onCurrencyChange(e.target.value)}
            aria-label="Currency"
            style={{ fontSize: '0.8rem', padding: '4px 8px' }}
          >
            <option value="INR">INR (₹)</option>
            <option value="USD">USD ($)</option>
            <option value="EUR">EUR (€)</option>
            <option value="GBP">GBP (£)</option>
          </select>

          {/* Theme toggle */}
          <button
            onClick={onToggleTheme}
            aria-label="Toggle theme"
            className="btn-outline"
            style={{ padding: '6px 10px' }}
          >
            {isDark ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
      </div>
    </header>
  );
};

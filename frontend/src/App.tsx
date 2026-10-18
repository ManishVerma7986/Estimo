import React, { useState, useEffect } from 'react';
import { Navbar, NavTab } from './components/Navbar';
import { DashboardPage } from './pages/DashboardPage';
import { DatasetsPage } from './pages/DatasetsPage';
import { TrainingPage } from './pages/TrainingPage';
import { ModelsPage } from './pages/ModelsPage';
import { EstimatePage } from './pages/EstimatePage';
import { ScenariosPage } from './pages/ScenariosPage';
import { ReportsPage } from './pages/ReportsPage';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<NavTab>('dashboard');
  const [currency, setCurrency] = useState('INR'); // Rule R7: Default INR, configurable
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
  }, [isDark]);

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* WCAG AA Skip to Main Content */}
      <a
        href="#main-content"
        style={{
          position: 'absolute',
          left: '-9999px',
          top: 'auto',
          width: '1px',
          height: '1px',
          overflow: 'hidden',
          zIndex: 999,
        }}
        onFocus={(e) => {
          e.currentTarget.style.left = '10px';
          e.currentTarget.style.top = '10px';
          e.currentTarget.style.width = 'auto';
          e.currentTarget.style.height = 'auto';
          e.currentTarget.style.background = '#2563eb';
          e.currentTarget.style.color = '#fff';
          e.currentTarget.style.padding = '8px 16px';
        }}
        onBlur={(e) => {
          e.currentTarget.style.left = '-9999px';
        }}
      >
        Skip to main content
      </a>

      <Navbar
        currentTab={currentTab}
        onTabChange={setCurrentTab}
        currency={currency}
        onCurrencyChange={setCurrency}
        isDark={isDark}
        onToggleTheme={() => setIsDark(!isDark)}
      />

      <main id="main-content" style={{ flex: 1, paddingBottom: '60px' }}>
        {currentTab === 'dashboard' && <DashboardPage onNavigate={setCurrentTab} currency={currency} />}
        {currentTab === 'datasets' && <DatasetsPage />}
        {currentTab === 'training' && <TrainingPage />}
        {currentTab === 'models' && <ModelsPage />}
        {currentTab === 'estimate' && <EstimatePage currency={currency} />}
        {currentTab === 'scenarios' && <ScenariosPage currency={currency} />}
        {currentTab === 'reports' && <ReportsPage currency={currency} />}
      </main>

      <footer
        style={{
          borderTop: '1px solid var(--border)',
          background: 'var(--bg-surface)',
          padding: '16px 20px',
          textAlign: 'center',
          fontSize: '0.8rem',
          color: 'var(--text-muted)',
        }}
      >
        Estimo 3.0 &bull; Production-Quality Offline-Capable Cost Engine &bull; Built with FastAPI &amp; React
      </footer>
    </div>
  );
};

import React from 'react';
import { Database, AlertCircle } from 'lucide-react';

interface EmptyStateProps {
  title?: string;
  message?: string;
  actionText?: string;
  onAction?: () => void;
  icon?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title = "No dataset loaded",
  message = "Import a dataset to begin.",
  actionText,
  onAction,
  icon,
}) => {
  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '60px 20px',
        textAlign: 'center',
        border: '2px dashed var(--border)',
        borderRadius: 'var(--radius-lg)',
        background: 'var(--bg-surface)',
        margin: '20px 0',
      }}
    >
      <div
        style={{
          width: '56px',
          height: '56px',
          borderRadius: '50%',
          background: 'var(--primary-light)',
          color: 'var(--primary)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: '16px',
        }}
      >
        {icon || <Database size={28} />}
      </div>
      <h3 style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: '6px', color: 'var(--text-primary)' }}>
        {title}
      </h3>
      <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', maxWidth: '420px', marginBottom: actionText ? '20px' : '0' }}>
        {message}
      </p>
      {actionText && onAction && (
        <button onClick={onAction} className="btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
          {actionText}
        </button>
      )}
    </div>
  );
};

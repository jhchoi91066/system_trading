"use client";

import { useTranslation } from 'react-i18next';
import { useClientOnly } from '../hooks/useClientOnly';

export function LocalizedPageTitle({ className = "" }: { className?: string }) {
  const { t } = useTranslation();
  const isClient = useClientOnly();

  if (!isClient) {
    return <h1 className={`text-h1 text-center mb-12 ${className}`}>Trading Dashboard</h1>;
  }

  return <h1 className={`text-h1 text-center mb-12 ${className}`}>{t('nav.dashboard')}</h1>;
}

export function LocalizedSectionTitle({ sectionKey, className = "" }: { sectionKey: string; className?: string }) {
  const { t } = useTranslation();
  const isClient = useClientOnly();

  if (!isClient) {
    return <h2 className={`text-h3 mb-6 ${className}`}>Loading...</h2>;
  }

  return <h2 className={`text-h3 mb-6 ${className}`}>{t(sectionKey)}</h2>;
}

export function LocalizedSelectLabel({ labelKey }: { labelKey: string }) {
  const { t } = useTranslation();
  const isClient = useClientOnly();

  if (!isClient) {
    return <label className="block text-small mb-2">:</label>;
  }

  return <label className="block text-small mb-2">{t(labelKey)}:</label>;
}

export function LocalizedButton({ 
  textKey, 
  loadingKey, 
  loading = false, 
  className = "", 
  ...props 
}: { 
  textKey: string; 
  loadingKey?: string; 
  loading?: boolean; 
  className?: string; 
  [key: string]: any;
}) {
  const { t } = useTranslation();
  const isClient = useClientOnly();

  if (!isClient) {
    return (
      <button 
        className={`linear-button-primary py-3 px-8 disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
        disabled={loading}
        {...props}
      >
        {loading ? 'Loading...' : 'Button'}
      </button>
    );
  }

  return (
    <button 
      className={`linear-button-primary py-3 px-8 disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
      disabled={loading}
      {...props}
    >
      {loading && loadingKey ? t(loadingKey) : t(textKey)}
    </button>
  );
}

export function LocalizedText({ textKey, values, className = "" }: { textKey: string; values?: any; className?: string }) {
  const { t } = useTranslation();
  const isClient = useClientOnly();

  if (!isClient) {
    return <span className={className}>...</span>;
  }

  return <span className={className}>{t(textKey, values)}</span>;
}

export function LocalizedTableHeader({ headers }: { headers: string[] }) {
  const { t } = useTranslation();
  const isClient = useClientOnly();

  if (!isClient) {
    return (
      <thead className="glass-medium">
        <tr>
          {headers.map((header, index) => (
            <th key={index} scope="col" className="px-6 py-3 text-left text-caption text-secondary uppercase tracking-wider">
              ...
            </th>
          ))}
        </tr>
      </thead>
    );
  }

  return (
    <thead className="glass-medium">
      <tr>
        {headers.map((header, index) => (
          <th key={index} scope="col" className="px-6 py-3 text-left text-caption text-secondary uppercase tracking-wider">
            {t(header)}
          </th>
        ))}
      </tr>
    </thead>
  );
}
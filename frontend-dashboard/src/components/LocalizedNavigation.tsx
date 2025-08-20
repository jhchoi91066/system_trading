"use client";

import { useTranslation } from 'react-i18next';
import { useClientOnly } from '../hooks/useClientOnly';

export function LocalizedNavigationLinks({ isMobile = false }: { isMobile?: boolean }) {
  const { t } = useTranslation();
  const isClient = useClientOnly();

  const navStyle = isMobile ? {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '8px',
    padding: '16px',
    backgroundColor: '#1e293b',
    borderTop: '1px solid #64748b'
  } : {
    display: 'flex',
    alignItems: 'center',
    gap: '24px'
  };

  const linkStyle = isMobile ? {
    display: 'block',
    padding: '8px 16px',
    fontSize: '14px',
    color: '#d1d5db',
    textDecoration: 'none',
    fontWeight: '500',
    borderRadius: '4px',
    transition: 'all 0.2s ease'
  } : {
    color: '#d1d5db',
    textDecoration: 'none',
    padding: '8px 12px',
    fontSize: '14px',
    fontWeight: '600',
    borderBottom: '2px solid transparent',
    transition: 'all 0.2s ease'
  };

  if (!isClient) {
    return (
      <nav style={navStyle}>
        <a href="/" style={linkStyle}>Dashboard</a>
        <a href="/strategies" style={linkStyle}>Strategies</a>
        <a href="/backtest" style={linkStyle}>Backtest</a>
        <a href="/trading-history" style={linkStyle}>Trading History</a>
        <a href="/fund-management" style={linkStyle}>Fund Management</a>
        <a href="/api-keys" style={linkStyle}>API Keys</a>
        <a href="/monitoring" style={linkStyle}>Monitoring</a>
        <a href="/notifications" style={linkStyle}>Notifications</a>
        <a href="/settings" style={linkStyle}>Settings</a>
      </nav>
    );
  }

  return (
    <nav style={navStyle}>
      <a href="/" style={linkStyle}>{t('nav.dashboard')}</a>
      <a href="/strategies" style={linkStyle}>{t('nav.strategies')}</a>
      <a href="/backtest" style={linkStyle}>{t('nav.backtest')}</a>
      <a href="/trading-history" style={linkStyle}>{t('nav.tradingHistory')}</a>
      <a href="/fund-management" style={linkStyle}>{t('nav.fundManagement')}</a>
      <a href="/api-keys" style={linkStyle}>{t('nav.apiKeys')}</a>
      <a href="/monitoring" style={linkStyle}>{t('nav.monitoring')}</a>
      <a href="/notifications" style={linkStyle}>{t('nav.notifications')}</a>
      <a href="/settings" style={linkStyle}>{t('common.settings')}</a>
    </nav>
  );
}

export function LocalizedAuthButtons() {
  const { t } = useTranslation();
  const isClient = useClientOnly();

  if (!isClient) {
    return (
      <>
        <button className="linear-button-secondary px-4 py-2">Sign In</button>
        <button className="linear-button-primary px-4 py-2">Sign Up</button>
      </>
    );
  }

  return (
    <>
      <button className="linear-button-secondary px-4 py-2">{t('nav.signIn')}</button>
      <button className="linear-button-primary px-4 py-2">{t('nav.signUp')}</button>
    </>
  );
}

export function LocalizedTitle() {
  const { t } = useTranslation();
  const isClient = useClientOnly();

  const titleStyle = {
    fontSize: '20px',
    color: '#ffffff',
    fontWeight: '500',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    margin: '0'
  };

  if (!isClient) {
    return <h1 style={titleStyle}>Bitcoin Trading</h1>;
  }
  
  return (
    <h1 style={titleStyle}>{t('dashboard.title')}</h1>
  );
}
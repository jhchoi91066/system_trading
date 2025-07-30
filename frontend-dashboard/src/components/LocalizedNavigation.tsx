"use client";

import { useTranslation } from 'react-i18next';
import { useClientOnly } from '../hooks/useClientOnly';

export function LocalizedNavigationLinks({ isMobile = false }: { isMobile?: boolean }) {
  const { t } = useTranslation();
  const isClient = useClientOnly();

  const navClasses = isMobile ? "flex flex-col space-y-2 p-4 bg-gray-800" : "flex items-center space-x-6";
  const linkClasses = isMobile ? "linear-nav-link-mobile" : "linear-nav-link";

  if (!isClient) {
    return (
      <nav className={navClasses}>
        <a href="/" className={linkClasses}>Dashboard</a>
        <a href="/strategies" className={linkClasses}>Strategies</a>
        <a href="/backtest" className={linkClasses}>Backtest</a>
        <a href="/trading-history" className={linkClasses}>Trading History</a>
        <a href="/fund-management" className="linear-nav-link">Fund Management</a>
        <a href="/api-keys" className={linkClasses}>API Keys</a>
        <a href="/monitoring" className={linkClasses}>Monitoring</a>
        <a href="/notifications" className={linkClasses}>Notifications</a>
        <a href="/settings" className={linkClasses}>Settings</a>
      </nav>
    );
  }

  return (
    <nav className={navClasses}>
      <a href="/" className={linkClasses}>{t('nav.dashboard')}</a>
      <a href="/strategies" className={linkClasses}>{t('nav.strategies')}</a>
      <a href="/backtest" className={linkClasses}>{t('nav.backtest')}</a>
      <a href="/trading-history" className={linkClasses}>{t('nav.tradingHistory')}</a>
      <a href="/fund-management" className={linkClasses}>{t('nav.fundManagement')}</a>
      <a href="/api-keys" className={linkClasses}>{t('nav.apiKeys')}</a>
      <a href="/monitoring" className={linkClasses}>{t('nav.monitoring')}</a>
      <a href="/notifications" className={linkClasses}>{t('nav.notifications')}</a>
      <a href="/settings" className={linkClasses}>{t('common.settings')}</a>
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

  if (!isClient) {
    return <h1 className="text-h3 text-white font-medium">Bitcoin Trading</h1>;
  }
  
  return (
    <h1 className="text-h3 text-white font-medium">{t('dashboard.title')}</h1>
  );
}
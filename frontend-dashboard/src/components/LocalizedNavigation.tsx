"use client";

import { useTranslation } from 'react-i18next';
import { useClientOnly } from '../hooks/useClientOnly';

export function LocalizedNavigationLinks() {
  const { t } = useTranslation();
  const isClient = useClientOnly();

  if (!isClient) {
    return (
      <nav className="flex items-center space-x-6">
        <a href="/" className="linear-nav-link">Dashboard</a>
        <a href="/strategies" className="linear-nav-link">Strategies</a>
        <a href="/api-keys" className="linear-nav-link">API Keys</a>
        <a href="/monitoring" className="linear-nav-link">Monitoring</a>
        <a href="/notifications" className="linear-nav-link">Notifications</a>
      </nav>
    );
  }

  return (
    <nav className="flex items-center space-x-6">
      <a href="/" className="linear-nav-link">{t('nav.dashboard')}</a>
      <a href="/strategies" className="linear-nav-link">{t('nav.strategies')}</a>
      <a href="/api-keys" className="linear-nav-link">{t('nav.apiKeys')}</a>
      <a href="/monitoring" className="linear-nav-link">{t('nav.monitoring')}</a>
      <a href="/notifications" className="linear-nav-link">{t('nav.notifications')}</a>
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
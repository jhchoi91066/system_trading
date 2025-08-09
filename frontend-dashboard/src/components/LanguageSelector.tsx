"use client";

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useClientOnly } from '../hooks/useClientOnly';

const LanguageSelector = () => {
  const { i18n, t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const isClient = useClientOnly();

  const languages = [
    { code: 'en', name: 'English', flag: '🇺🇸' },
    { code: 'ko', name: '한국어', flag: '🇰🇷' },
  ];

  const currentLanguage = languages.find(lang => lang.code === i18n.language) || languages[0];

  const changeLanguage = (languageCode: string) => {
    i18n.changeLanguage(languageCode);
    setIsOpen(false);
  };

  if (!isClient) {
    return (
      <div className="relative">
        <button
          className="flex items-center space-x-2 px-3 py-2 rounded-lg bg-white hover:bg-gray-50 transition-colors border border-gray-300 text-gray-700"
          disabled
        >
          <span className="text-lg">🇺🇸</span>
          <span className="text-sm font-medium hidden sm:block">English</span>
        </button>
      </div>
    );
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center space-x-2 px-3 py-2 rounded-lg bg-white hover:bg-gray-50 transition-colors border border-gray-300 text-gray-700"
        aria-label={t('common.language')}
      >
        <span className="text-lg">{currentLanguage.flag}</span>
        <span className="text-sm font-medium hidden sm:block">{currentLanguage.name}</span>
        <svg 
          className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} 
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div 
            className="fixed inset-0 z-10" 
            onClick={() => setIsOpen(false)}
          />
          
          {/* Dropdown */}
          <div className="absolute right-0 mt-2 py-2 w-48 bg-white rounded-lg shadow-xl border border-gray-200 z-20">
            {languages.map((language) => (
              <button
                key={language.code}
                onClick={() => changeLanguage(language.code)}
                className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-100 transition-colors flex items-center space-x-3 ${
                  currentLanguage.code === language.code 
                    ? 'bg-gray-100 text-green-600' 
                    : 'text-gray-700 hover:text-gray-900'
                }`}
              >
                <span className="text-lg">{language.flag}</span>
                <span>{language.name}</span>
                {currentLanguage.code === language.code && (
                  <svg className="w-4 h-4 ml-auto text-green-600" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                )}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
};

export default LanguageSelector;
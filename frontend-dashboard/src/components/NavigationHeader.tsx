"use client";

import { useState } from 'react';
import {
  SignInButton,
  SignUpButton,
  SignedIn,
  SignedOut,
  UserButton,
} from "@clerk/nextjs";
import LanguageSelector from "@/components/LanguageSelector";
import { LocalizedNavigationLinks, LocalizedAuthButtons, LocalizedTitle } from "@/components/LocalizedNavigation";

export default function NavigationHeader() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const headerStyle = {
    backgroundColor: '#1e293b',
    borderBottom: '1px solid #64748b',
    padding: '24px',
    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    minHeight: '80px'
  };

  const containerStyle = {
    maxWidth: '1280px',
    margin: '0 auto',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between'
  };

  const leftSectionStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: '32px'
  };

  const rightSectionStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: '16px'
  };

  const hamburgerStyle = {
    color: '#d1d5db',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    padding: '4px'
  };

  return (
    <header style={headerStyle}>
      <div style={containerStyle}>
        <div style={leftSectionStyle}>
          <LocalizedTitle />
          {/* Desktop Navigation Links */}
          <div style={{display: 'block'}}>
            <LocalizedNavigationLinks />
          </div>
        </div>
        <div style={rightSectionStyle}>
          <LanguageSelector />
          <AuthButtons />
          {/* Hamburger Menu Button for Mobile */}
          <div style={{display: 'none'}}>
            <button onClick={() => setIsMenuOpen(!isMenuOpen)} style={hamburgerStyle}>
              <svg style={{width: '24px', height: '24px'}} fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16"></path>
              </svg>
            </button>
          </div>
        </div>
      </div>
      {/* Mobile Navigation Menu */}
      {isMenuOpen && (
        <div style={{marginTop: '16px'}}>
          <LocalizedNavigationLinks isMobile={true} />
        </div>
      )}
    </header>
  );
}

function AuthButtons() {
  return (
    <>
      <SignedOut>
        <SignInButton mode="modal">
          <button className="linear-button-secondary px-4 py-2">Sign In</button>
        </SignInButton>
        <SignUpButton mode="modal">
          <button className="linear-button-primary px-4 py-2">Sign Up</button>
        </SignUpButton>
      </SignedOut>
      <SignedIn>
        <UserButton 
          appearance={{
            elements: {
              avatarBox: "w-8 h-8",
              userButtonPopoverCard: "bg-slate-800 border border-slate-600 shadow-lg",
              userButtonPopoverActionButton: "text-gray-300 hover:text-white hover:bg-slate-700"
            }
          }}
        />
      </SignedIn>
    </>
  );
}
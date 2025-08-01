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

  return (
    <header className="linear-nav p-6 border-b border-opacity-10 border-white">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <div className="flex items-center space-x-8">
          <LocalizedTitle />
          {/* Desktop Navigation Links */}
          <SignedIn>
            <div className="hidden md:flex">
              <LocalizedNavigationLinks />
            </div>
          </SignedIn>
        </div>
        <div className="flex items-center space-x-4">
          <LanguageSelector />
          <AuthButtons />
          {/* Hamburger Menu Button for Mobile */}
          <div className="md:hidden">
            <button onClick={() => setIsMenuOpen(!isMenuOpen)} className="text-white focus:outline-none">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16"></path>
              </svg>
            </button>
          </div>
        </div>
      </div>
      {/* Mobile Navigation Menu */}
      {isMenuOpen && (
        <div className="md:hidden mt-4">
          <SignedIn>
            <LocalizedNavigationLinks isMobile={true} />
          </SignedIn>
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
              userButtonPopoverCard: "bg-gray-900 border border-gray-700",
              userButtonPopoverActionButton: "text-gray-300 hover:text-white hover:bg-gray-800"
            }
          }}
        />
      </SignedIn>
    </>
  );
}
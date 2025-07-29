import type { Metadata } from "next";
import {
  ClerkProvider,
  SignInButton,
  SignUpButton,
  SignedIn,
  SignedOut,
  UserButton,
} from "@clerk/nextjs";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import I18nProvider from "./providers/I18nProvider";
import { WebSocketProvider } from "@/contexts/WebSocketProvider";
import LanguageSelector from "@/components/LanguageSelector";
import { LocalizedNavigationLinks, LocalizedAuthButtons, LocalizedTitle } from "@/components/LocalizedNavigation";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Bitcoin Trading Dashboard",
  description: "Advanced cryptocurrency trading dashboard with backtesting and real-time data",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body
          className={`${geistSans.variable} ${geistMono.variable} antialiased`}
        >
          <I18nProvider>
            <WebSocketProvider>
              <MainLayout>{children}</MainLayout>
            </WebSocketProvider>
          </I18nProvider>
        </body>
      </html>
    </ClerkProvider>
  );
}

function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <NavigationHeader />
      {children}
    </>
  );
}

function NavigationHeader() {
  return (
    <header className="linear-nav p-6 border-b border-opacity-10 border-white">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <div className="flex items-center space-x-8">
          <LocalizedTitle />
          <SignedIn>
            <LocalizedNavigationLinks />
          </SignedIn>
        </div>
        <div className="flex items-center space-x-4">
          <LanguageSelector />
          <AuthButtons />
        </div>
      </div>
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
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
          <header className="linear-nav p-6 border-b border-opacity-10 border-white">
            <div className="max-w-7xl mx-auto flex items-center justify-between">
              <div className="flex items-center space-x-8">
                <h1 className="text-h3 text-white font-medium">Bitcoin Trading</h1>
                <SignedIn>
                  <nav className="flex items-center space-x-6">
                    <a href="/" className="linear-nav-link">Dashboard</a>
                    <a href="/strategies" className="linear-nav-link">Strategies</a>
                    <a href="/api-keys" className="linear-nav-link">API Keys</a>
                    <a href="/monitoring" className="linear-nav-link">Monitoring</a>
                    <a href="/notifications" className="linear-nav-link">Notifications</a>
                  </nav>
                </SignedIn>
              </div>
              <div className="flex items-center space-x-4">
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
              </div>
            </div>
          </header>
          {children}
        </body>
      </html>
    </ClerkProvider>
  );
}
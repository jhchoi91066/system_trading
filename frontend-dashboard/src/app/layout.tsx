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
import { WebSocketProvider } from '@/contexts/WebSocketProvider';
import { LocalizedNavigationLinks, LocalizedAuthButtons, LocalizedTitle } from "@/components/LocalizedNavigation";
import NavigationHeader from "@/components/NavigationHeader";

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
          <WebSocketProvider>
            <MainLayout>{children}</MainLayout>
          </WebSocketProvider>
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



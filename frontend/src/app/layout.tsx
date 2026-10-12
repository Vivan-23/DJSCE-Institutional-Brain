import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/layout/Sidebar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "DJSCE Institutional Brain — Institutional Intelligence",
  description:
    "Institutional knowledge, governance decision-support and procedure intelligence platform (Demonstration Prototype for DJ Sanghvi College of Engineering).",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="h-screen w-screen flex flex-col lg:flex-row bg-slate-950 m-0 overflow-hidden text-slate-100">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0 min-h-0 h-full overflow-hidden bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
          {/* Persistent Academic Prototype Notice */}
          <header className="demo-banner px-3 sm:px-4 py-1.5 flex items-center justify-between text-xs text-slate-400 shrink-0 z-10">
            <div className="flex items-center gap-2 min-w-0">
              <span className="w-2 h-2 rounded-full bg-amber-400 inline-block shrink-0" />
              <span className="font-semibold text-slate-300 tracking-wide uppercase text-[10px] shrink-0">
                Demonstration Prototype
              </span>
              <span className="text-slate-500 hidden sm:inline">·</span>
              <span className="truncate text-[11px] text-slate-400">
                Not an official college system, ERP, or authorized deployment
              </span>
            </div>
            <div className="hidden md:flex items-center gap-2 text-[11px] text-slate-400 shrink-0">
              <span>Dwarkadas J. Sanghvi College of Engineering</span>
              <span className="text-slate-600">|</span>
              <span className="font-mono text-slate-400 text-[10px]">Decision Support</span>
            </div>
          </header>

          {/* Primary Viewport Scroll Area */}
          <div className="flex-1 overflow-y-auto overflow-x-hidden min-h-0">
            {children}
          </div>
        </div>
      </body>
    </html>
  );
}

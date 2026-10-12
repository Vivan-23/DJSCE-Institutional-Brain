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
      <body className="min-h-full flex bg-slate-950 m-0 overflow-hidden text-slate-100">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
          {/* Persistent Academic Prototype Notice */}
          <header className="demo-banner px-4 py-1.5 flex items-center justify-between text-xs text-slate-400 shrink-0">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-amber-400 inline-block shrink-0" />
              <span className="font-semibold text-slate-300 tracking-wide uppercase text-[10px]">
                Demonstration Prototype
              </span>
              <span className="text-slate-500">·</span>
              <span className="truncate">Not an official college system, ERP, or authorized deployment</span>
            </div>
            <div className="hidden sm:flex items-center gap-3 text-[11px] text-slate-400">
              <span>Dwarkadas J. Sanghvi College of Engineering</span>
              <span className="text-slate-600">|</span>
              <span className="font-mono text-slate-400">Research &amp; Decision Support</span>
            </div>
          </header>

          <div className="flex-1 overflow-auto">
            {children}
          </div>
        </div>
      </body>
    </html>
  );
}

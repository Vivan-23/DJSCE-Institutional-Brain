import type { Metadata } from "next";
import { Inter, Geist_Mono } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/layout/Sidebar";

const inter = Inter({
  variable: "--font-inter",
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
      className={`${inter.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="h-screen w-screen flex flex-col lg:flex-row bg-slate-950 m-0 overflow-hidden text-slate-100 text-[13px]">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0 min-h-0 h-full lg:h-[calc(100%-1rem)] overflow-hidden bg-[#0f1011] lg:m-2 lg:rounded-lg lg:border lg:border-white/[0.07] lg:shadow-[0_0_0_1px_rgba(0,0,0,0.4),0_8px_24px_rgba(0,0,0,0.35)]">
          {/* Persistent Academic Prototype Notice */}
          <header className="demo-banner px-4 sm:px-5 h-9 flex items-center justify-between text-xs text-slate-400 shrink-0 z-10">
            <div className="flex items-center gap-2 min-w-0">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 inline-block shrink-0" />
              <span className="font-medium text-slate-300 text-[12px] shrink-0">
                Demonstration prototype
              </span>
              <span className="text-slate-500 hidden sm:inline">·</span>
              <span className="truncate text-[12px] text-slate-500">
                Not an official college system, ERP, or authorized deployment
              </span>
            </div>
            <div className="hidden md:flex items-center gap-2 text-[12px] text-slate-500 shrink-0">
              <span>Dwarkadas J. Sanghvi College of Engineering</span>
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

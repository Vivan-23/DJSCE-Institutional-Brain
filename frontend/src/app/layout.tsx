import type { Metadata } from "next";
import { Inter, Geist_Mono } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/layout/Sidebar";
import { THEME_INIT_SCRIPT } from "@/lib/themeScript";

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
      suppressHydrationWarning
      className={`${inter.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        <script id="theme-init" dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="h-screen w-screen flex flex-col lg:flex-row bg-slate-950 m-0 overflow-hidden text-slate-100 text-[0.8125rem]">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0 min-h-0 h-full lg:h-[calc(100%-1rem)] overflow-hidden bg-[var(--surface)] lg:m-2 lg:rounded-lg lg:border lg:border-white/[0.07] lg:shadow-[0_0_0_1px_rgba(0,0,0,0.4),0_8px_24px_rgba(0,0,0,0.35)]">
          {/* Primary Viewport Scroll Area */}
          <div className="flex-1 overflow-y-auto overflow-x-hidden min-h-0">
            {children}
          </div>
        </div>
      </body>
    </html>
  );
}

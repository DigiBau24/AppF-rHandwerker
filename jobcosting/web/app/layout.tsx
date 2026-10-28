import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "Job-Costing", description: "Nachkalkulation für Handwerksbetriebe" };
export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body className="bg-slate-100 text-slate-900 antialiased">{children}</body>
    </html>
  );
}

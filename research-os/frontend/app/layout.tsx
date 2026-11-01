import "./globals.css";
import type { ReactNode } from "react";

export const metadata = { title: "Research OS", description: "Project-based AI research workspace" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

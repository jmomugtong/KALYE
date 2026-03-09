import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "KALYE - Walkability Intelligence",
  description: "AI-powered walkability scoring for Metro Manila",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

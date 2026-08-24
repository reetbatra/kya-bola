import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "kya bola?",
  description:
    "Where Indian speech recognition actually works, district by district and language by language.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

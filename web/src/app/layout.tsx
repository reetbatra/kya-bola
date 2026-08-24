import type { Metadata } from "next";
import { Newsreader, Inter } from "next/font/google";
import "./globals.css";

// Newsreader is designed for long-form reading; Inter carries the tables and
// controls, where tabular figures matter more than warmth.
const serif = Newsreader({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-serif",
  display: "swap",
});

const sans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "kya bola?",
  description:
    "Where Indian speech recognition actually works, district by district and language by language.",
  openGraph: {
    title: "kya bola?",
    description:
      "India speaks 64 languages in this dataset. Speech APIs support 19. Measured district by district.",
    type: "article",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${serif.variable} ${sans.variable}`}>
      <body>
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-[var(--surface)] focus:px-4 focus:py-2 focus:outline-2 focus:outline-[var(--accent)]"
        >
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}

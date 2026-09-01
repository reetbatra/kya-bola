import type { Metadata, Viewport } from "next";
import { Newsreader, Inter } from "next/font/google";
import "./globals.css";
import { SiteNav } from "@/components/SiteNav";

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

// The page is a single committed light theme, so the browser chrome is told to
// match rather than being left to guess from the system setting.
export const viewport: Viewport = {
  themeColor: "#faf9f5",
  colorScheme: "light",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${serif.variable} ${sans.variable}`}>
      <body>
        <a href="#main" className="skip-link skip-link--page">
          Skip to content
        </a>
        <SiteNav />
        {children}
      </body>
    </html>
  );
}

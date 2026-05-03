import type { Metadata } from "next";
import GlobalSoundControls from "@/components/GlobalSoundControls";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI-SAATHI",
  description: "Gamified competitive learning platform with study plans, lessons, quizzes, progress, and profile insights.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        {children}
        <GlobalSoundControls />
      </body>
    </html>
  );
}

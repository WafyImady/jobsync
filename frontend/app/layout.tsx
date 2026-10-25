import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "JobSync",
  description: "Reverse ATS",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet" />
      </head>
      <body className="bg-[#031427] m-0 p-0">{children}</body>
    </html>
  );
}
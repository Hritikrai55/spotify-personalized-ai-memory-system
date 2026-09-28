import "./globals.css";

export const metadata = {
  title: "Spotify AI Memory Console",
  description: "Memory-enabled AI chat console",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

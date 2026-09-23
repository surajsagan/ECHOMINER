import type { Metadata } from "next";
import "./globals.css";
import { SITE } from "@/lib/site";

export const metadata: Metadata = {
  metadataBase: new URL(SITE.domain),
  title: {
    default: `${SITE.name} — ${SITE.tagline}`,
    template: `%s — ${SITE.name}`,
  },
  description: SITE.description,
  keywords: [
    "echocardiography", "structured data extraction", "natural language processing",
    "cardiovascular research", "JSS AHER", "DBT BUILDER", "health informatics",
  ],
  authors: [{ name: "Group 3, DBT-BUILDER, JSS AHER" }],
  alternates: { canonical: SITE.domain },
  openGraph: {
    type: "website",
    url: SITE.domain,
    siteName: SITE.name,
    title: `${SITE.name} — ${SITE.tagline}`,
    description: SITE.description,
    locale: "en_IN",
  },
  twitter: {
    card: "summary_large_image",
    title: `${SITE.name} — ${SITE.tagline}`,
    description: SITE.description,
  },
  robots: { index: true, follow: true },
};

const JSON_LD = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      name: "JSS Academy of Higher Education and Research",
      url: "https://jssuni.edu.in",
      department: { "@type": "Organization", name: "Department of Community Medicine, JSS Medical College" },
    },
    {
      "@type": "SoftwareApplication",
      name: SITE.name,
      applicationCategory: "ResearchApplication",
      operatingSystem: "Web",
      url: SITE.domain,
      description: SITE.description,
      offers: { "@type": "Offer", price: "0", priceCurrency: "INR" },
      identifier: "https://doi.org/10.5281/zenodo.21281483",
      funder: { "@type": "Organization", name: "Department of Biotechnology, Government of India" },
    },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-IN" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap"
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(JSON_LD) }}
        />
      </head>
      <body>
        <a
          href="#top"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-deep focus:px-4 focus:py-2 focus:text-white"
        >
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}

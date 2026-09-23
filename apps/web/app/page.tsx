import { SiteFooter, SiteHeader } from "@/components/chrome";
import { Hero } from "@/components/hero";
import {
  About, Cite, Contact, DbtProject, Faq, Features, News, Publications,
  ResearchImpact, Team, WhyStructured, Workflow,
} from "@/components/sections";
import { ToolSection } from "@/components/tool";

export default function HomePage() {
  return (
    <>
      <SiteHeader />
      <main id="main">
        <Hero />
        <About />
        <WhyStructured />
        <Features />
        <Workflow />
        <ToolSection />
        <DbtProject />
        <Team />
        <ResearchImpact />
        <Publications />
        <News />
        <Cite />
        <Faq />
        <Contact />
      </main>
      <SiteFooter />
    </>
  );
}

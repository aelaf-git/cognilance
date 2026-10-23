import ClickSpark from "@/components/ClickSpark";
import { Contact } from "@/components/Contact";
import { Faq } from "@/components/Faq";
import { Footer } from "@/components/Footer";
import { Hero } from "@/components/Hero";
import { About } from "@/components/About";
import { Integrations } from "@/components/Integrations";
import { Services } from "@/components/Services";
import { SiteHeader } from "@/components/SiteHeader";

export default function HomePage() {
  return (
    <ClickSpark
      sparkColor="#ffffff"
      sparkSize={10}
      sparkRadius={15}
      sparkCount={8}
      duration={400}
    >
      <SiteHeader overlay />
      <main>
        <Hero />
        <About />
        <Integrations />
        <Services />
        <Faq />
        <Contact />
      </main>
      <Footer />
    </ClickSpark>
  );
}

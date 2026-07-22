import ClickSpark from "@/components/ClickSpark";
import { BusinessModel } from "@/components/BusinessModel";
import { Developers } from "@/components/Developers";
import { Footer } from "@/components/Footer";
import { Hero } from "@/components/Hero";
import { HowItWorks } from "@/components/HowItWorks";
import { Market } from "@/components/Market";
import { Pricing } from "@/components/Pricing";
import { Problem } from "@/components/Problem";
import { Proof } from "@/components/Proof";
import { SiteHeader } from "@/components/SiteHeader";
import { Solution } from "@/components/Solution";
import { Team } from "@/components/Team";
import { Waitlist } from "@/components/Waitlist";

export default function HomePage() {
  return (
    <ClickSpark
      sparkColor="#ff492c"
      sparkSize={10}
      sparkRadius={15}
      sparkCount={8}
      duration={400}
    >
      <SiteHeader />
      <main>
        <Hero />
        <Proof />
        <Problem />
        <Solution />
        <HowItWorks />
        <BusinessModel />
        <Pricing />
        <Developers />
        <Market />
        <Team />
        <Waitlist />
      </main>
      <Footer />
    </ClickSpark>
  );
}

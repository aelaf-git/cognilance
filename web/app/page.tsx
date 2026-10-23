import ClickSpark from "@/components/ClickSpark";
import { BusinessModel } from "@/components/BusinessModel";
import { Footer } from "@/components/Footer";
import { Hero } from "@/components/Hero";
import { HowItWorks } from "@/components/HowItWorks";
import { Pricing } from "@/components/Pricing";
import { Problem } from "@/components/Problem";
import { SiteHeader } from "@/components/SiteHeader";
import { SocialProof } from "@/components/SocialProof";
import { Solution } from "@/components/Solution";
import { Team } from "@/components/Team";

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
        <SocialProof />
        <Problem />
        <Solution />
        <HowItWorks />
        <BusinessModel />
        <Pricing />
        <Team />
      </main>
      <Footer />
    </ClickSpark>
  );
}

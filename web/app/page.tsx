import { BusinessModel } from "@/components/BusinessModel";
import { Footer } from "@/components/Footer";
import { Hero } from "@/components/Hero";
import { HowItWorks } from "@/components/HowItWorks";
import { Market } from "@/components/Market";
import { Problem } from "@/components/Problem";
import { Proof } from "@/components/Proof";
import { SiteHeader } from "@/components/SiteHeader";
import { Solution } from "@/components/Solution";
import { Team } from "@/components/Team";
import { Waitlist } from "@/components/Waitlist";

export default function HomePage() {
  return (
    <>
      <SiteHeader />
      <main>
        <Hero />
        <Problem />
        <Proof />
        <Solution />
        <HowItWorks />
        <BusinessModel />
        <Market />
        <Team />
        <Waitlist />
      </main>
      <Footer />
    </>
  );
}

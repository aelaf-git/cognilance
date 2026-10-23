export const WAITLIST = "/waitlist";

export const OFFICE_MAPS = "https://maps.app.goo.gl/3CwxEVPkf9WyFR7L8";
export const OFFICE_NAME = "AI Startup Center";
export const OFFICE_STREET = "Yared Street";
export const OFFICE_LOCALITY = "Lideta, Addis Ababa, Ethiopia";
export const OFFICE_LANDMARK = "Next to the National Bank of Ethiopia";
export const OFFICE_LAT = 9.0185433;
export const OFFICE_LNG = 38.7516055;
export const OFFICE_MAP_EMBED = `https://www.google.com/maps?q=${OFFICE_LAT},${OFFICE_LNG}&z=17&output=embed`;

export const EMAIL = "cognilance@gmail.com";
export const PHONE = "+251 964 336 078";
export const PHONE_TEL = "+251964336078";

export const NAV_LINKS = [
  { href: "/#about", label: "About" },
  { href: "/#how", label: "How it works" },
  { href: "/#contact", label: "Contact" },
  { href: "/developers", label: "Developers" },
];

export const FOOTER_COLUMNS = [
  {
    title: "Product",
    links: [
      { href: "/#product", label: "Overview" },
      { href: "/#how", label: "How it works" },
      { href: "/#about", label: "About" },
      { href: WAITLIST, label: "Waitlist" },
    ],
  },
  {
    title: "Developers",
    links: [
      { href: "/developers", label: "SDK & docs" },
      { href: "/#faq", label: "FAQ" },
    ],
  },
  {
    title: "Company",
    links: [
      { href: "/#contact", label: "Contact" },
      { href: "/privacy", label: "Privacy" },
      { href: "/cookies", label: "Cookies" },
    ],
  },
];

export const LEGAL_LINKS = [
  { href: "/privacy", label: "Privacy policy" },
  { href: "/cookies", label: "Cookies" },
];

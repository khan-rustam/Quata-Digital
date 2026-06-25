/**
 * Illustration palette — Orange + Quata Blue.
 *
 * These are the *illustration* brand colours (per leadership's image-upgrade
 * brief): Primary Orange #FF6B00 + the Quata blue from the QUATAPAY logo.
 * They are intentionally independent of the site's CSS theme tokens so every
 * custom illustration reads as one cohesive, on-brand set regardless of the
 * surrounding UI chrome.
 *
 * Flat hex values only — illustrations avoid <defs>/url() gradients so the
 * same illustration can appear multiple times on a page without SVG id
 * collisions. "Depth" is faked with layered fills + opacity.
 */
export const C = {
  // Orange (primary)
  orange: "#FF6B00",
  orangeDark: "#E25E00",
  orangeMid: "#FF8A33",
  orangeSoft: "#FFD9BC",
  orangeTint: "#FFF1E6",

  // Quata blue (secondary)
  navy: "#0E2A6B",
  navyDeep: "#0A1F50",
  blue: "#1E63D6",
  blueMid: "#3D86E8",
  blueLight: "#69B6F2",
  blueSky: "#9AD2F8",
  blueSoft: "#DCEAFB",
  blueTint: "#EEF4FD",

  // Neutrals / surfaces
  ink: "#0F1216",
  slate: "#5B6470",
  steel: "#8B93A1",
  line: "#E6E9EF",
  lineSoft: "#EEF1F5",
  panel: "#FFFFFF",
  panelSoft: "#F6F8FB",
  panelMute: "#EFF2F7",
  white: "#FFFFFF",

  // Tertiary accents
  gold: "#E8B14A",
  goldSoft: "#F7E6BE",
  green: "#19A974",
  greenSoft: "#CdEfdF",
  red: "#E5484D",
  redSoft: "#FBD9DA",

  // African skin + hair tones for people illustrations (boss: subjects black)
  skin1: "#6E4A34",
  skin2: "#875436",
  skin3: "#A4683F",
  skin4: "#C0855A",
  hair: "#171311",
} as const;

export type IllustrationColor = keyof typeof C;

Warm Editorial Minimalism — Design System Specification

1. Core Aesthetic Philosophy
Warm Editorial Minimalism is a design system defined by the fusion of three core influences:
- Japanese Spatial Restraint: Intentional whitespace, calm surfaces, uncluttered layouts, and meticulous spatial discipline.
- Soft Brutalism's Structural Confidence: Crisp 1px structural borders, strong geometry, high-contrast typography, and uncompromising flat surface hierarchy.
- High-End Editorial Typographic Authority: Editorial publishing layout design, aggressive weight contrast, tight letter-spacing on display heads, and pristine print-inspired composition (inspired by jacobleech.com, simulate.com, minymon.com, and high-fashion print layouts).

Tone in One Sentence:
Every screen should feel like a beautifully designed product catalog from a Japanese studio that also reads Wallpaper magazine and builds software.

2. Absolute Visual Prohibitions (Hard Constraints)
Under no circumstances should any of the following visual tropes be implemented. Violating any rule breaks the integrity of the design system:
❌ NO Dark Mode as Default: The canvas is strictly warm and light.
❌ NO Neon or Over-Saturated Background Gradients: Avoid uncalibrated decorative background hues.
❌ NO Purple, Magenta, or "AI Product" Palettes: Avoid generic tech purple/indigo accents.
❌ NO Glowing Gradients, Aurora Effects, or Mesh Gradients: Decorative background gradients are strictly forbidden.
❌ NO Glassmorphism: No frosted glass, background blurs (backdrop-filter: blur()), or decorative glass panels.
❌ NO Deep Drop Shadows: No shadow-xl, shadow-2xl, or colored/glowing shadow effects.
❌ NO Pill-Shaped Buttons (rounded-full): Strictly forbidden on primary action buttons or structural components.
❌ NO Standard "SaaS Dashboard" Visual Tropes: No dark navigation rails, no purple sidebars, no glowing KPI cards.
❌ NO Decorative Canvas Gradients: The canvas background must remain a single, flat, warm tone (#E8E4D3 Warm Ivory).
❌ NO Heavy Border-Radius on Structural Components: Cards and containers are not bubbly panels.
❌ NO Emoji-Heavy UI: Use crisp line icons (1.5px stroke) or text-based indicators only.

3. Core Color System

3.1 Background (The Canvas)
The canvas must evoke high-quality uncoated editorial paper—warm, natural, and non-clinical.

| Role | Hex Code | Tailwind Equivalent | Description |
| :--- | :--- | :--- | :--- |
| Primary Canvas | #E8E4D3 | bg-[#E8E4D3] | Warm Ivory canvas. Primary page background. |
| Alternate Canvas | #DFDBCA | bg-[#DFDBCA] | Slightly deeper warm ivory tone for section contrast. |

3.2 Accent System (Primary Actions & Highlights)
Accent color usage is sparse—maximum 1 to 2 appearances per screen. Accent functions as a gentle whisper, never a shout.

| Accent Role | Hex Code | Tailwind Class | Application |
| :--- | :--- | :--- | :--- |
| Primary Accent | #00AEBB | bg-[#00AEBB]/15 | Soft fills, drop zone hover backgrounds, subtle active state indicators. |
| Action Accent | #00AEBB | border-[#00AEBB] / bg-[#00AEBB] | Active borders, button highlights, interactive focus bounds. |
| Text on Accent | #FFFFFF | text-white | High-contrast readable text inside Electric Teal containers or buttons. |
| Focused Accent | #00AEBB | ring-[#00AEBB] / border-[#00AEBB] | Ring indicators, active focus states only. |

3.3 Typography Colors

| Role | Hex Code | Tailwind Class | Application |
| :--- | :--- | :--- | :--- |
| Primary Text | #031211 | text-[#031211] | Ink Black. All main headings, component labels, primary body content. |
| Secondary Text | #5C584E | text-[#5C584E] | Subtitles, field descriptions, placeholders, metadata. |
| Disabled / Hint | #9E988A | text-[#9E988A] | Inactive text, ghost elements, subtle timestamps. |

3.4 Borders & Dividers

| Type | Specification / Class | Application |
| :--- | :--- | :--- |
| Default Border | #D8D3C3 / border-[#D8D3C3] | Standard card bounds, structural containers. |
| Subtle Divider | #E0DCCC / border-[#E0DCCC] | Internal row dividers, horizontal rules within panels. |
| Emphasis Border | #031211 at 10% opacity / border-[#031211]/10 | High-contrast structural boundaries. |
| Dashed Border | border-dashed border-[#C5C0B0] | Drag-and-drop upload containers, media placeholding zones. |

3.5 Surface Colors

| Surface | Hex Code / Tailwind | Purpose |
| :--- | :--- | :--- |
| Card Surface | #FFFFFF (bg-white) | Flat white paper sheets floating on the Warm Ivory canvas. |
| Elevated Surface | #F4F1E6 (bg-[#F4F1E6]) | Slightly elevated secondary side panels or secondary blocks. |
| Input Surface | #FFFFFF or transparent | Clean form inputs. Never grey filled backgrounds. |

4. Typography System
Typography carries the structural load of the entire layout. Aggressive contrast between heavy headlines and thin body text produces visual rhythm.

4.1 Font Stack Definitions
```css
/* Headings — High-impact, editorial geometric sans-serif */
font-family: 'Inter', 'DM Sans', 'Geist', system-ui, sans-serif;

/* Body — Legible, neutral workhorse sans-serif */
font-family: 'Inter', 'DM Sans', system-ui, sans-serif;

/* Accent / Serif Moments — High-fashion editorial accent (max 1 per screen) */
font-family: 'Playfair Display', 'DM Serif Display', 'Lora', Georgia, serif;

/* Mono — Code blocks, IDs, technical specifications, uppercase metadata */
font-family: 'JetBrains Mono', 'Fira Code', 'Geist Mono', monospace;
```

4.2 Typographic Scale & Rules

| Level | Font Size | Font Weight | Letter Spacing (Tracking) | Tailwind / CSS Reference |
| :--- | :--- | :--- | :--- | :--- |
| Display / Hero | 56–72px | 800–900 (Black) | -0.03em | text-5xl md:text-7xl font-black tracking-tight text-[#031211] |
| Section Heading | 28–36px | 700 (Bold) | -0.02em | text-2xl md:text-4xl font-bold tracking-tight text-[#031211] |
| Component Title | 18–22px | 600 (Semi-Bold) | -0.01em | text-lg md:text-xl font-semibold tracking-tight text-[#031211] |
| UI Label | 12–13px | 500 (Medium) | 0.05–0.1em (UPPERCASE) | text-xs font-medium tracking-widest uppercase text-[#5C584E] |
| Body Text | 14–16px | 400 (Regular) | Normal (line-height: 1.7) | text-sm md:text-base font-normal leading-relaxed text-[#031211] |
| Caption / Meta | 11–12px | 400 (Regular) | Normal | text-xs font-normal text-[#9E988A] |

4.3 Editorial Typographic Rules
- Weight Contrast: Combine ultra-bold (800–900) headlines with light/regular (400) body text to establish high editorial tension.
- Negative Letter-Spacing: Always apply tracking-tight (-0.02em to -0.03em) on titles larger than 24px.
- Uppercase Labels: Small metadata tags, field labels, section badges, and step counts must be formatted in text-xs tracking-widest uppercase font-medium text-[#5C584E].
- Serif Accent Rule: Limit serif typography (Playfair Display, Lora) strictly to pull quotes, key metrics, or hero taglines. Maximum one serif instance per screen.
- Measure (Line Length): Wrap paragraph blocks at max-width: 65ch (max-w-prose) to preserve optimal editorial eye travel.
- Alignment Constraint: Align body text left. Centering is strictly reserved for hero titles or brief metadata badges.

5. Component System

5.1 Buttons
Primary Action Button
- Background: bg-[#031211]
- Text: text-white
- Border Radius: rounded-sm (2px) or rounded (4px) — NEVER rounded-full
- Padding: px-6 py-2.5
- Font: text-sm font-medium tracking-wide
- Hover State: hover:bg-[#031211]/85 transition-colors

Secondary / Outlined Button
- Background: transparent
- Border: border border-[#C5C0B0]
- Text: text-[#031211]
- Border Radius: rounded-sm or rounded
- Hover State: hover:bg-[#E8E4D3]/40 hover:border-[#031211] transition-colors

Accent Button
- Background: bg-[#00AEBB]
- Border: border border-[#00AEBB]
- Text: text-white
- Border Radius: rounded-sm or rounded
- Hover State: hover:bg-[#00AEBB]/90 transition-colors

Ghost / Destructive Button
- Background: transparent
- Text: text-[#5C584E]
- Hover State: hover:text-[#031211] hover:bg-[#E8E4D3]/50 transition-colors

5.2 Input Fields & Forms
- Base Structure: bg-white or bg-transparent, border border-[#C5C0B0], rounded-sm or rounded (4–6px max radius).
- Padding & Font: px-3 py-2 or px-4 py-2.5, text-sm text-[#031211].
- Placeholder: placeholder:text-[#9E988A].
- Focus State: focus:outline-none focus:ring-1 focus:ring-[#00AEBB] focus:border-[#00AEBB].
- Field Labels: text-xs font-medium tracking-wider uppercase text-[#5C584E] mb-1 block.
- Strict Don'ts: No rounded-lg or rounded-xl on inputs. No filled grey input backgrounds. No multi-colored glowing focus indicators.

5.3 Cards & Containers
- Background: bg-white (pure flat paper contrast against #E8E4D3 Warm Ivory).
- Border: border border-[#D8D3C3].
- Shadow: shadow-sm ONLY. Never heavy ambient shadows.
- Border Radius: rounded-lg (8–12px max).
- Padding: p-5 or p-6 (generous inner breathing space).

5.4 Upload & Drop Zones
- Background: bg-[#00AEBB]/5 or transparent.
- Border: border-2 border-dashed border-[#C5C0B0].
- Border Radius: rounded-lg.
- Hover State: hover:border-[#00AEBB] hover:bg-[#00AEBB]/10 transition-colors.
- Active Drag State: border-[#00AEBB] bg-[#00AEBB]/20.
- Content Styling: text-[#9E988A], sparse instructional text.

5.5 Chat & Messaging Bubbles
- User Bubble: bg-[#00AEBB]/10 border border-[#00AEBB]/20 text-[#031211] rounded-lg p-4
- AI / Assistant Bubble: bg-white border border-[#D8D3C3] text-[#031211] rounded-lg p-4
- Timestamps: text-xs text-[#9E988A] font-normal mt-1
- Constraint: No floating glass cards or multi-colored gradients.

5.6 Navigation (Top Bar / Sidebar)
- Background: bg-[#E8E4D3] or bg-white (never dark).
- Border: border-b border-[#D8D3C3] (Top Bar) or border-r border-[#D8D3C3] (Sidebar).
- Brand Logo: text-[#031211] font-semibold text-lg tracking-tight.
- Nav Links: text-sm text-[#5C584E] hover:text-[#031211] transition-colors.
- Active State: text-[#031211] font-medium (indicated by structural text weight, never pill shapes or glowing background caps).

5.7 Loading & Feedback Indicators
- Spinner: Simple line circular spinner in #D8D3C3 with active stroke in #031211.
- Pulse State: Soft pulsing dot or indicator bar formatted in bg-[#00AEBB] animate-pulse.
- Skeleton Screen: bg-[#DFDBCA] animate-pulse rounded (flat, neutral warm tone).
- Progress Bar: Container bg-[#E0DCCC], fill bg-[#00AEBB], h-1 (4px height), flat ends (no rounded-full).
- Prohibition: No neon pulse rings, particle emitters, or multi-colored progress bars.

6. Layout & Spacing System

6.1 Grid & Container Rules
- Container Max Width: max-w-6xl (1152px) for standardized content containers.
- Horizontal Padding: Mobile px-6 $\rightarrow$ Desktop px-12.
- Vertical Section Spacing: py-16 to py-24 between major blocks.
- Grid Gap Standard: gap-4, gap-6, or gap-8.

6.2 Spatial Philosophy
- Whitespace as Active Element: Generous negative space ensures the Warm Ivory canvas (#E8E4D3) remains visible, framed by white structural cards.
- Grid Alignment: Strictly follow an 8px spatial step grid (8px, 16px, 24px, 32px, 48px, 64px).
- Layout Structure: Prefer asymmetrical editorial splits (e.g., 40/60 column grids, offset image blocks) over monotonous symmetrical grids. Left alignment is default.

7. 3D & Motion System (Showcase / Gallery Views)

7.1 3D Card Stack Guidelines
```css
/* Container Perspective */
.perspective-container {
  perspective: 1200px;
  transform-style: preserve-3d;
}

/* Card Transformation */
.card-3d {
  /* Calculated per index step N */
  transform: translateX(calc(var(--index) * 20px)) 
             translateZ(calc(var(--index) * -40px)) 
             rotateY(calc(var(--index) * -4deg));
  transition: all 0.6s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 4px 16px rgba(3, 18, 17, 0.08); /* Soft, realistic shadow */
}

.card-3d:hover {
  transform: translateY(-4px) scale(1.02);
}
```
- Card Appearance: Flat white card surface (#FFFFFF). Top 75-80% assigned to editorial imagery/media.
- Shadow Rule: Controlled, soft drop shadow (0 4px 16px rgba(3,18,17,0.08)). No neon glowing ambient shadows.

7.2 Motion Principles
- Timing Curves: Use cubic-bezier(0.4, 0, 0.2, 1) for smooth, architectural transitions.
- Duration Standard: 300ms–600ms for layout transitions; 200ms for micro-interactions (hovers, button clicks).
- Prohibition: No spring physics, bouncy overshoots, high-velocity flings, or particle systems.

8. Admin & Dashboard Panels
- Overall Background: Flat #E8E4D3 warm canvas.
- Sidebar: bg-white border-r border-[#D8D3C3] w-64 p-6.
- Form Headers: text-xs font-semibold tracking-widest uppercase text-[#9E988A] border-b border-[#D8D3C3] pb-2 mb-4 block.
- Form Layout: Vertically stacked inputs with standard gap-4 (16px).
- Data Tables:
  - Header Row: bg-[#DFDBCA] text-xs font-medium uppercase tracking-widest text-[#5C584E] border-b border-[#D8D3C3] py-3 px-4 text-left.
  - Body Rows: bg-white border-b border-[#E0DCCC] text-sm text-[#031211] py-3 px-4.
  - Row Hover: hover:bg-[#E8E4D3]/40 transition-colors.

9. Responsive Breakpoint Rules

| Viewport | Range | Layout Specs | Typographic Adjustments |
| :--- | :--- | :--- | :--- |
| Mobile | < 640px | Single-column layout. Cards scale to 100% width. Touch targets minimum 44px. Preserve Warm Ivory canvas background. | Reduce display titles by 30–40% (text-3xl max display scale). |
| Tablet | 640px – 1024px | 2-column grid structure. Adaptive sidebar collapsible to top menu. | Medium scale headers (text-4xl). |
| Desktop | > 1024px | Full multi-column layout (3–4 column grids). Asymmetrical editorial column blocks. | Full display scale (56px–72px editorial display headers). |

10. Iconography
- Style: Crisp, clean outline/line icons only (e.g., Lucide Icons, Heroicons Outline). No filled, gradient, or rounded-blob icon vectors.
- Stroke Width: Strictly 1.5px.
- Sizing Rules:
  - Inline / Micro: 16px (w-4 h-4)
  - Buttons / Actions: 20px (w-5 h-5)
  - Feature Highlights: 24px (w-6 h-6)
- Color Assignment: text-[#5C584E] by default; text-[#031211] for active/selected states.

11. Copywriting & Voice Guidelines
- Headings: Direct, confident, editorial, and noun-led.
  - Correct: "Image Processing Engine." | "Spatial Systems." | "Transform your image."
  - Incorrect: "Let's get started!" | "Welcome to our cool tool!"
- Descriptions: Minimalist and sparse. Maximum one concise sentence per description. Zero marketing jargon or filler text.
- Action CTAs: Direct action verbs.
  - Correct: "Upload" | "Generate" | "Export" | "Submit"
  - Incorrect: "Let's go!" | "Start the magic!" | "Try now for free!"
- Empty & Error States: Clear, instructional, quiet, and specific. Avoiding alarmist messaging or dramatic emoji graphics.

12. Quick Reference Cheatsheet

| Design Element | DO THIS ✅ | NOT THIS ❌ |
| :--- | :--- | :--- |
| Canvas Background | bg-[#E8E4D3] Warm Ivory | Pure white, cool grey, dark mode, or background gradients |
| Primary Text | text-[#031211] (Ink Black) | Stark pure #000000, soft blue-grey, or colored text |
| Accent Highlights | Electric Teal #00AEBB | Saturated purple, neon pink, electric orange |
| Buttons | rounded-sm flat #031211 or line border | rounded-full pills, glowing gradient buttons |
| Cards & Surfaces | Pure White (#FFFFFF) + border-[#D8D3C3] + shadow-sm | Glassmorphism, blurred backdrop, ambient dark card |
| Input Fields | White background, border-[#C5C0B0], rounded-sm | Grey background (bg-gray-100), heavy rounded-xl radius |
| Headings | Weight 700–900, negative letter-spacing (tracking-tight) | Standard medium weight, generic sans serif without tracking |
| Loading Indicators | Minimal line spinner, Electric Teal #00AEBB pulse bar | Glowing neon rings, futuristic progress bars |
| Shadows | shadow-sm only | Heavy shadow-xl, shadow-2xl, glowing shadows |
| Corner Radii | rounded-sm (2-4px) to rounded-lg (8-12px) max | rounded-full on structural components or cards |
| Motion & Transitions | Smooth cubic-bezier(0.4, 0, 0.2, 1) (300-600ms) | Springy overshoot physics, particle effects |
| Icons | Outline line icons, 1.5px stroke weight | Solid filled icons, multi-color icons, emojis |
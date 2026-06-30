# Prompt 24: High-End Premium Landing Page & Apple/Manthan-Inspired UI
Context: The landing home page needs an aesthetic upgrade to match Apple's hardware reveal pages and premium interactive portals like Manthan. It must feature ultra-clean layouts, cinematic transitions, a high-density "Bento Grid" feature showcase, and subtle typography masks.
Task: Redesign `frontend/src/app/page.tsx` into a high-fidelity visual experience.

Requirements:
1. **Cinematic Hero Section:**
   - Implement a dark, immersive background (`bg-black` or deep `#09090b` zinc) featuring an elegant radial gradient spotlight tracking the mouse position or centered behind the heading.
   - Use dynamic typography masks with subtle animations. The main headline ("Engineering Intelligence. Deciphered.") should feature a muted metallic gradient text clip.
   - Add a premium micro-interaction to the CTAs: a glossy glassmorphism button ("Get Started") that uses an absolute-positioned border glow, paired with an elegant text link ("Request a Demo →").

2. **The "Bento Grid" Feature Showcase:**
   - Below the fold, replace standard feature lists with a dynamic asymmetric Bento grid structure inspired by modern Apple feature breakdowns.
   - **Grid Card 1 (2x2 span):** A large interactive module previewing the multi-hop Incident Investigation graph network animating elements dynamically.
   - **Grid Card 2 (1x2 span):** A high-contrast miniature data graphic showing real-time Knowledge Risk Assessment (KRA) alerts changing from green to crimson.
   - **Grid Card 3 (1x1 span):** A clean interface window snippet showcasing automated Employee Exit handover documentation assembling line-by-line.

3. **Interactive "Scroll-to-Reveal" Hardware feel:**
   - Integrate subtle reveal animations (using `framer-motion` or standard tailwind intersection observers).
   - As elements enter the viewport, scale them up smoothly from `0.95` to `1` and fade them in to mimic premium design standards.
   - Include a sticky dark navigation bar at the top with a high-blur backdrop (`backdrop-blur-md bg-black/40`) containing a clean typography logo, links to features, and an entry login trigger.

4. **Preserve Auth Routing Hooks:** Ensure the underlying authentication modals (OAuth, Signup/Login state changes) built in previous steps remain completely integrated into these updated interactive design triggers.
# Prompt 26: Moving Authentication from Dialog Modals to Dedicated Pages
Context: To provide an enterprise-grade experience that aligns with our premium Apple/Manthan-inspired homepage, authentication must be moved out of popup dialog boxes into dedicated, distraction-free sub-pages (`/login` and `/signup`).
Task: Create standalone frontend authentication routes and refactor routing entry points.

Requirements:

1. **New Route Foundations:**
   - Create two new App Router page directories: `frontend/src/app/login/page.tsx` and `frontend/src/app/signup/page.tsx`.
   - Remove the old inline popup auth dialog modals and state variables from the home landing workspace (`frontend/src/app/page.tsx`).

2. **Premium Interface Design Layout:**
   - Design both screens with an elegant, minimalist layout: a split-pane configuration or a centered, floating glassmorphism card wrapped in an immersive dark background (`bg-black`).
   - On the left side (or background), display subtle, slow-moving ambient gradients with a clean marketing typography statement: *"Engineering intelligence, decoded. Welcome back."*
   - On the dynamic right side (or form container), render input controls featuring ultra-crisp focus rings, clear social sign-on layout buttons ("Continue with Google", "Continue with GitHub"), and text field states for email and password inputs.

3. **Multi-Tenant Navigation Mapping:**
   - On successful login, check the user session context. Route existing managers straight to the default `/dashboard`.
   - On successful email or social signup, dynamically create their new system workspace container and automatically push their client session to the redesigned `/onboarding` pipeline layout.
   - Include intuitive lower navigation links on the screens to let users toggle fluidly between the routes (e.g., *"New here? Create an account"* or *"Already have an enterprise space? Log in"*).
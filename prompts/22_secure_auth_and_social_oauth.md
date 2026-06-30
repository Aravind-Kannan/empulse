# Prompt 22: Traditional Secure Auth & Google/GitHub OAuth2 Integrations
Context: The landing screen auth dialogue requires upgrading from mock components to production-ready secure identity flows supporting native password signup and social sign-on providers.
Task: Create the backend auth handlers and frontend UI wiring for password, Google, and GitHub authentication.

Requirements:
1. **Password Signup/Login Security:**
   - In the auth system, add a secure password text input field. On the backend, use `passlib` with `bcrypt` to securely hash and verify passwords before storage.
2. **Social Sign-On Providers (OAuth2):**
   - Integrate authentication flows using standard libraries (e.g., `Auth.js` / `NextAuth` on the frontend or FastAPI's `authlib`).
   - Add clear branding action buttons: "Continue with Google" and "Continue with GitHub" to the auth layout component.
3. **Dynamic Tenant Creation on Signup:**
   - When a user signs up using a fresh account (Password or Social OAuth), automatically generate a new `Tenant` record alongside their `User` entry.
   - On successful validation, sign a cryptographically secure JWT cookie token packed with both `user_id` and `tenant_id` payloads.
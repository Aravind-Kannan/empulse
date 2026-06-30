export interface AuthSession {
  email: string;
  name: string;
  company: string;
  isNewUser: boolean;
  onboarded: boolean;
  loggedInAt: string;
}

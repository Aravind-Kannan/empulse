import { AuthForm } from "@/components/auth/AuthForm";
import { AuthScreenLayout } from "@/components/auth/AuthScreenLayout";

export default function SignupPage() {
  return (
    <AuthScreenLayout mode="signup">
      <AuthForm mode="signup" />
    </AuthScreenLayout>
  );
}

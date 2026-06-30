import { AuthForm } from "@/components/auth/AuthForm";
import { AuthScreenLayout } from "@/components/auth/AuthScreenLayout";

export default function LoginPage() {
  return (
    <AuthScreenLayout mode="login">
      <AuthForm mode="login" />
    </AuthScreenLayout>
  );
}

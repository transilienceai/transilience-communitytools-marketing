import { SignUp } from "@clerk/nextjs";

export default function SignUpPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0f0f0f]">
      <SignUp forceRedirectUrl="/dashboard" />
    </div>
  );
}

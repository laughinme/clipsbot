import { type ComponentProps, type FormEvent } from "react"

import { Button } from "@/shared/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/components/ui/card"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldError,
  FieldLabel,
} from "@/shared/components/ui/field"
import { Input } from "@/shared/components/ui/input"
import { cn } from "@/shared/lib/utils"

type SignupFormProps = Omit<ComponentProps<"div">, "onSubmit"> & {
  email: string
  password: string
  onEmailChange: (value: string) => void
  onPasswordChange: (value: string) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void | Promise<void>
  submitLabel: string
  disabled?: boolean
  submitDisabled?: boolean
  errorMessage?: string | null
  onSwitchToLogin: () => void
}

export function SignupForm({
  className,
  email,
  password,
  onEmailChange,
  onPasswordChange,
  onSubmit,
  submitLabel,
  disabled = false,
  submitDisabled = false,
  errorMessage,
  onSwitchToLogin,
  ...props
}: SignupFormProps) {
  return (
    <div
      className={cn("flex flex-col gap-6 text-neutral-200", className)}
      {...props}
    >
      <Card className="bg-neutral-900 border-neutral-800 shadow-none">
        <CardHeader className="space-y-2 text-center">
          <CardTitle className="text-xl font-semibold text-white">
            Create your account
          </CardTitle>
          <CardDescription className="text-sm text-neutral-400">
            Enter your details to get started
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-6">
            <FieldGroup>
              {errorMessage ? <FieldError>{errorMessage}</FieldError> : null}
              <Field>
                <FieldLabel
                  htmlFor="email"
                  className="text-sm font-medium text-neutral-200"
                >
                  Email
                </FieldLabel>
                <Input
                  id="email"
                  type="email"
                  placeholder="m@example.com"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(event) => onEmailChange(event.target.value)}
                  disabled={disabled}
                  className="bg-neutral-950 border-neutral-800 text-neutral-100 placeholder:text-neutral-500"
                />
              </Field>
              <Field>
                <FieldLabel
                  htmlFor="password"
                  className="text-sm font-medium text-neutral-200"
                >
                  Password
                </FieldLabel>
                <Input
                  id="password"
                  type="password"
                  required
                  autoComplete="new-password"
                  value={password}
                  onChange={(event) => onPasswordChange(event.target.value)}
                  disabled={disabled}
                  className="bg-neutral-950 border-neutral-800 text-neutral-100 placeholder:text-neutral-500"
                />
                <FieldDescription className="text-neutral-500">
                  Must be at least 8 characters long.
                </FieldDescription>
              </Field>
              <Field>
                <Button
                  type="submit"
                  disabled={submitDisabled || disabled}
                  className="bg-white text-neutral-900 hover:bg-neutral-200 disabled:bg-neutral-700 disabled:text-neutral-400"
                >
                  {submitLabel}
                </Button>
                <FieldDescription className="text-center text-sm text-neutral-400">
                  Already have an account?{" "}
                  <button
                    type="button"
                    onClick={onSwitchToLogin}
                    className="underline-offset-4 hover:underline text-white"
                  >
                    Sign in
                  </button>
                </FieldDescription>
              </Field>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
      <FieldDescription className="px-6 text-center text-sm text-neutral-500">
        By clicking continue, you agree to our{" "}
        <a className="text-neutral-300" href="#">
          Terms of Service
        </a>{" "}
        and{" "}
        <a className="text-neutral-300" href="#">
          Privacy Policy
        </a>
        .
      </FieldDescription>
    </div>
  )
}

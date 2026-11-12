"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Button, Notice, Segmented, TextInput } from "@/components/ui";
import { api, ApiError, errorText } from "@/lib/api/client";
import type { SignInOptions } from "@/lib/api/types";
import { config } from "@/lib/config";
import { useAccount } from "./AccountContext";
import s from "./AccountDialog.module.css";

type Mode = "login" | "signup";
const modes: { value: Mode; label: string }[] = [
  { value: "login", label: "Log in" },
  { value: "signup", label: "Sign up" },
];

interface Problem {
  /** The field the server named (sign-up), else the error shows under the form. */
  field?: string;
  message: string;
}

/** Log in or sign up; a sign-up error shows under the field it is about. */
export function AuthForm({ onDone }: { onDone: (mode: Mode) => void }) {
  const { logIn, signUp } = useAccount();
  const [mode, setMode] = useState<Mode>("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  // Email links and Google show only when the server has them set up.
  const [options, setOptions] = useState<
    Pick<SignInOptions, "link" | "google">
  >({ link: false, google: false });
  const [linkSent, setLinkSent] = useState<number | null>(null);
  const [sending, setSending] = useState(false);
  useEffect(() => {
    let live = true;
    api
      .signInOptions()
      .then((o) => live && setOptions({ link: o.link, google: o.google }))
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);

  const sendLink = async () => {
    setSending(true);
    setProblem(null);
    try {
      setLinkSent((await api.sendSignInLink(email.trim())).minutes);
    } catch (err) {
      setProblem({
        field: err instanceof ApiError ? err.field : undefined,
        message: errorText(err, "That didn't go through. Try again."),
      });
    } finally {
      setSending(false);
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setProblem(null);
    try {
      if (mode === "login") await logIn(email.trim(), password);
      else await signUp(email.trim(), name.trim(), password);
      onDone(mode);
    } catch (err) {
      setProblem({
        field: err instanceof ApiError ? err.field : undefined,
        message: errorText(err, "That didn't go through. Try again."),
      });
    } finally {
      setBusy(false);
    }
  };

  /** The field's error in the field's hint slot (read with the field), else its usual hint. */
  const hint = (field: string, usual?: string) =>
    problem?.field === field ? (
      <span className={s.fieldError}>{problem.message}</span>
    ) : (
      usual
    );
  const invalid = (field: string) => problem?.field === field || undefined;

  return (
    <form className={s.stack} onSubmit={submit} noValidate>
      <Segmented
        label="Log in or sign up"
        hideLabel
        options={modes}
        value={mode}
        onChange={(m) => {
          setMode(m);
          setProblem(null);
        }}
      />
      {mode === "signup" && (
        <TextInput
          label="Name"
          autoComplete="name"
          maxLength={config.account.nameMax}
          value={name}
          hint={hint("name")}
          aria-invalid={invalid("name")}
          onChange={(e) => setName(e.target.value)}
        />
      )}
      <TextInput
        label="Email"
        type="email"
        autoComplete="email"
        value={email}
        hint={hint("email")}
        aria-invalid={invalid("email")}
        onChange={(e) => setEmail(e.target.value)}
      />
      <TextInput
        label="Password"
        type="password"
        autoComplete={mode === "login" ? "current-password" : "new-password"}
        value={password}
        hint={hint(
          "password",
          mode === "signup"
            ? `At least ${config.account.passwordMin} characters.`
            : undefined,
        )}
        aria-invalid={invalid("password")}
        onChange={(e) => setPassword(e.target.value)}
      />
      {problem && !problem.field && (
        <Notice kind="error">{problem.message}</Notice>
      )}
      <Button
        type="submit"
        variant="primary"
        block
        busy={busy}
        busyLabel={mode === "login" ? "Logging in…" : "Creating your account…"}
      >
        {mode === "login" ? "Log in" : "Create account"}
      </Button>
      {(options.link || options.google) && (
        <div className={s.stack}>
          <p className={s.or}>or, without a password</p>
          {options.link &&
            (linkSent ? (
              <p role="status" className={s.sent}>
                Check your inbox: we&apos;ve sent a sign-in link to{" "}
                {email.trim()}. It works once, for {linkSent} minutes.
              </p>
            ) : (
              <Button
                block
                busy={sending}
                busyLabel="Sending…"
                disabled={!email.trim()}
                onClick={sendLink}
              >
                Email me a sign-in link
              </Button>
            ))}
          {options.google && (
            <a className={s.google} href={config.routes.google}>
              Continue with Google
            </a>
          )}
        </div>
      )}
      <p className={s.muted}>
        Optional. Practice works the same without one; an account keeps your
        skill history, saved prospects and saved questions.
      </p>
    </form>
  );
}

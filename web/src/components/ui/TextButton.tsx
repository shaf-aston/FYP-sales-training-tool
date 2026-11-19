import type { ButtonHTMLAttributes } from "react";
import s from "./TextButton.module.css";

/** A button that reads as a link in running text: a quiet way in ("Try a sample call", "Log in"). */
export function TextButton({ className, ...rest }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button type="button" {...rest} className={[s.text, className].filter(Boolean).join(" ")} />;
}

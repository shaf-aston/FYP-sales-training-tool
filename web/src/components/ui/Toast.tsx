"use client";

import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { config } from "@/lib/config";
import s from "./Toast.module.css";

type Kind = "info" | "success" | "error";
interface ToastMsg {
  id: number;
  text: string;
  kind: Kind;
}

const ToastContext = createContext<(text: string, kind?: Kind) => void>(() => {});

/** One toast at a time, announced to screen readers, auto-dismissed. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ToastMsg | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const show = useCallback((text: string, kind: Kind = "info") => {
    clearTimeout(timer.current);
    setToast({ id: Date.now(), text, kind });
    timer.current = setTimeout(() => setToast(null), config.toastMs);
  }, []);

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className={s.region} role="status" aria-live="polite">
        {toast && (
          <div key={toast.id} className={`${s.toast} ${s[toast.kind]}`}>
            {toast.text}
          </div>
        )}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);

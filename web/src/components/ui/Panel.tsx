import type { ReactNode } from "react";
import s from "./Panel.module.css";

interface Props {
  kicker: string;
  title: string;
  onClose?: () => void;
  /** Hide the header on phones (when the content already names itself). */
  hideHeadOnPhone?: boolean;
  children: ReactNode;
}

/** Side panel shell: kicker, title, close button and a scrolling body. */
export function Panel({ kicker, title, onClose, hideHeadOnPhone, children }: Props) {
  return (
    <aside className={s.panel} aria-label={title}>
      <header className={hideHeadOnPhone ? `${s.head} ${s.phoneHidden}` : s.head}>
        <div>
          <p className={s.kicker}>{kicker}</p>
          <h2 className={s.title}>{title}</h2>
        </div>
        {onClose && (
          <button type="button" className={s.close} onClick={onClose} aria-label={`Close ${title}`}>
            Close
          </button>
        )}
      </header>
      <div className={s.body}>{children}</div>
    </aside>
  );
}

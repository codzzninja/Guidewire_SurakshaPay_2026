import { useEffect, useId, useRef, useState } from "react";
import { useNotifications } from "../lib/NotificationContext";

function formatRelative(at: number): string {
  const s = Math.floor((Date.now() - at) / 1000);
  if (s < 60) return "Just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

const variantDot: Record<string, string> = {
  success: "bg-emerald-500",
  error: "bg-red-500",
  info: "bg-brand",
};

export default function NotificationBell() {
  const panelId = useId();
  const btnRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const { items, unreadCount, markRead, markAllRead, clear } =
    useNotifications();

  useEffect(() => {
    if (!open) return;
    markAllRead();
  }, [open, markAllRead]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const onPointer = (e: MouseEvent | TouchEvent) => {
      const t = e.target as Node;
      if (
        panelRef.current?.contains(t) ||
        btnRef.current?.contains(t)
      ) {
        return;
      }
      setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("touchstart", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("touchstart", onPointer);
    };
  }, [open]);

  return (
    <div className="relative shrink-0">
      <button
        ref={btnRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="relative min-h-[44px] min-w-[44px] flex items-center justify-center rounded-xl text-slate-600 hover:bg-slate-100/90 transition-colors"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={
          unreadCount > 0
            ? `Notifications, ${unreadCount} unread`
            : "Notifications"
        }
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="22"
          height="22"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden
        >
          <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
          <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
        </svg>
        {unreadCount > 0 ? (
          <span className="absolute top-1.5 right-1.5 min-w-[18px] h-[18px] px-1 flex items-center justify-center rounded-full bg-brand text-[10px] font-bold text-white">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        ) : null}
      </button>

      {open ? (
        <div
          ref={panelRef}
          id={panelId}
          role="dialog"
          aria-label="Notification list"
          className="absolute right-0 top-[calc(100%+6px)] z-[110] w-[min(100vw-2rem,20rem)] max-h-[min(70vh,24rem)] flex flex-col rounded-2xl border border-slate-200/90 bg-white shadow-xl overflow-hidden"
        >
          <div className="flex items-center justify-between gap-2 px-3 py-2.5 border-b border-slate-100 bg-slate-50/80">
            <p className="text-xs font-semibold text-slate-700 uppercase tracking-wide">
              Inbox
            </p>
            {items.length > 0 ? (
              <button
                type="button"
                onClick={() => clear()}
                className="text-xs font-medium text-brand hover:underline"
              >
                Clear all
              </button>
            ) : null}
          </div>
          <ul className="overflow-y-auto flex-1 p-1">
            {items.length === 0 ? (
              <li className="px-3 py-8 text-center text-sm text-slate-500">
                No notifications yet. Actions like subscribing, payouts, and
                demos appear here.
              </li>
            ) : (
              items.map((n) => (
                <li key={n.id}>
                  <button
                    type="button"
                    onClick={() => markRead(n.id)}
                    className={`w-full text-left rounded-xl px-3 py-2.5 transition hover:bg-slate-50 ${
                      n.read ? "opacity-90" : ""
                    }`}
                  >
                    <div className="flex gap-2">
                      <span
                        className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                          variantDot[n.variant] ?? variantDot.info
                        }`}
                        aria-hidden
                      />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-slate-900 leading-snug">
                          {n.title}
                        </p>
                        {n.body ? (
                          <p className="text-xs text-slate-600 mt-0.5 leading-relaxed">
                            {n.body}
                          </p>
                        ) : null}
                        <p className="text-[10px] text-slate-400 mt-1">
                          {formatRelative(n.at)}
                        </p>
                      </div>
                    </div>
                  </button>
                </li>
              ))
            )}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

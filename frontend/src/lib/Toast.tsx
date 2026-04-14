import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";

type Variant = "success" | "error" | "info";

type Item = { id: number; message: string; variant: Variant };

const ToastCtx = createContext<
  ((message: string, variant?: Variant) => void) | null
>(null);

const styles: Record<Variant, string> = {
  success:
    "bg-emerald-50 border-emerald-200/80 text-emerald-950 shadow-emerald-900/5",
  error: "bg-red-50 border-red-200/80 text-red-900 shadow-red-900/5",
  info: "bg-slate-900 border-slate-800 text-white shadow-slate-900/20",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Item[]>([]);

  const show = useCallback((message: string, variant: Variant = "info") => {
    const id = Date.now() + Math.random();
    setItems((prev) => [...prev, { id, message, variant }]);
    window.setTimeout(() => {
      setItems((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  }, []);

  return (
    <ToastCtx.Provider value={show}>
      {children}
      <div
        className="fixed inset-x-0 bottom-0 z-[100] pointer-events-none flex flex-col items-stretch gap-2 px-4 pb-safe safe-pb max-w-lg mx-auto w-full"
        role="region"
        aria-label="Toasts"
        aria-live="polite"
      >
        {items.map((t) => (
          <div
            key={t.id}
            role="status"
            className={`pointer-events-auto rounded-2xl border px-4 py-3 text-sm font-medium shadow-lg toast-enter ${styles[t.variant]}`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastCtx);
  if (!ctx) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return ctx;
}

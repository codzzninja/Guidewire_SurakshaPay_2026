import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type NotificationVariant = "success" | "error" | "info";

export type NotificationItem = {
  id: string;
  title: string;
  body: string;
  variant: NotificationVariant;
  read: boolean;
  at: number;
};

const STORAGE_KEY = "sp_notifications_v1";
const MAX_ITEMS = 40;

function loadStored(): NotificationItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (x): x is NotificationItem =>
        typeof x === "object" &&
        x !== null &&
        typeof (x as NotificationItem).id === "string" &&
        typeof (x as NotificationItem).at === "number"
    );
  } catch {
    return [];
  }
}

function saveStored(items: NotificationItem[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  } catch {
    /* quota / private mode */
  }
}

type Ctx = {
  items: NotificationItem[];
  unreadCount: number;
  add: (o: {
    title: string;
    body: string;
    variant: NotificationVariant;
  }) => void;
  markRead: (id: string) => void;
  markAllRead: () => void;
  clear: () => void;
};

const NotificationCtx = createContext<Ctx | null>(null);

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<NotificationItem[]>(() =>
    typeof window !== "undefined" ? loadStored() : []
  );

  useEffect(() => {
    saveStored(items);
  }, [items]);

  const add = useCallback(
    (o: { title: string; body: string; variant: NotificationVariant }) => {
      const row: NotificationItem = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
        title: o.title,
        body: o.body,
        variant: o.variant,
        read: false,
        at: Date.now(),
      };
      setItems((prev) => [row, ...prev].slice(0, MAX_ITEMS));
    },
    []
  );

  const markRead = useCallback((id: string) => {
    setItems((prev) =>
      prev.map((x) => (x.id === id ? { ...x, read: true } : x))
    );
  }, []);

  const markAllRead = useCallback(() => {
    setItems((prev) => prev.map((x) => ({ ...x, read: true })));
  }, []);

  const clear = useCallback(() => {
    setItems([]);
  }, []);

  const unreadCount = useMemo(
    () => items.filter((x) => !x.read).length,
    [items]
  );

  const v = useMemo(
    () => ({ items, unreadCount, add, markRead, markAllRead, clear }),
    [items, unreadCount, add, markRead, markAllRead, clear]
  );

  return (
    <NotificationCtx.Provider value={v}>{children}</NotificationCtx.Provider>
  );
}

export function useNotifications() {
  const ctx = useContext(NotificationCtx);
  if (!ctx) {
    throw new Error("useNotifications must be used within NotificationProvider");
  }
  return ctx;
}

import { useCallback } from "react";
import { useToast } from "./Toast";
import type { NotificationVariant } from "./NotificationContext";
import { useNotifications } from "./NotificationContext";

/**
 * Shows a toast and appends to the notification inbox (persisted in localStorage).
 * Pass title + body, or leave title empty to use body as the main line only.
 */
export function useNotify() {
  const toast = useToast();
  const { add } = useNotifications();

  return useCallback(
    (title: string, body: string, variant: NotificationVariant = "info") => {
      const toastText =
        title && body ? `${title}: ${body}` : title || body;
      toast(toastText, variant);

      const inboxTitle = title || body;
      const inboxBody = title ? body : "";
      add({ title: inboxTitle, body: inboxBody, variant });
    },
    [toast, add]
  );
}

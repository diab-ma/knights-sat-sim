import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader,
  AlertDialogTitle, AlertDialogDescription, AlertDialogFooter,
  AlertDialogCancel, AlertDialogAction,
} from "@/components/ui/alert-dialog";
import type { Progress, ResetProgressRequest } from "@/api/schema";

export function ResetProgress() {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function reset() {
    if (pending) return;
    setPending(true);
    setError("");
    setMessage("");
    try {
      const body: ResetProgressRequest = { confirm: "RESET DEMO PROGRESS" };
      const response = await fetch("/api/progress/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        const data = await response.json();
        const code = data?.error?.code;
        setError(code === "SESSION_ACTIVE"
          ? "Stop the active session before resetting progress."
          : code === "STORAGE_UNAVAILABLE"
            ? "Progress could not be reset. You can try again."
            : "Reset was refused. Refresh the page before trying again.");
        return;
      }
      const progress: Progress = await response.json();
      if (!Array.isArray(progress.completed_challenge_ids) || progress.completed_challenge_ids.length !== 0) {
        throw new Error("Unexpected reset response");
      }
      setOpen(false);
      setMessage("Shared demo progress has been reset.");
      // Refresh any server-backed catalogue/progress consumers without reloading drafts.
      window.dispatchEvent(new CustomEvent("progress-reset", { detail: progress }));
    } catch {
      setError("The reset outcome is unknown. Check progress before trying again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section aria-label="Demo progress" className="mt-4">
      <AlertDialog open={open} onOpenChange={(value) => {
        if (!pending) { setOpen(value); setError(""); }
      }}>
        <AlertDialogTrigger render={<Button variant="outline" size="sm" />}>
          Reset demo progress
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reset shared demo progress?</AlertDialogTitle>
            <AlertDialogDescription>
              This clears completion for all three Challenges for everyone using this demo.
              Workspace files are kept. Stop any active session first.
            </AlertDialogDescription>
          </AlertDialogHeader>
          {error && <p role="alert">{error}</p>}
          <AlertDialogFooter>
            <AlertDialogCancel disabled={pending}>Cancel</AlertDialogCancel>
            <AlertDialogAction variant="destructive" disabled={pending} onClick={reset}>
              {pending ? "Resetting…" : "Confirm reset"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      {message && <p role="status">{message}</p>}
    </section>
  );
}

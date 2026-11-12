import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ResetProgress } from "./ResetProgress";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

async function open() {
  render(<ResetProgress />);
  fireEvent.click(screen.getByRole("button", { name: "Reset demo progress" }));
  await screen.findByRole("alertdialog");
}

describe("Reset demo progress", () => {
  it("does not send a request when cancelled", async () => {
    const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
    await open();
    expect(screen.getByText(/all three Challenges/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect(fetch).not.toHaveBeenCalled();
  });

  it("sends explicit confirmation and reports saved reset", async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ completed_challenge_ids: [] }) });
    vi.stubGlobal("fetch", fetch);
    await open();
    expect(fetch).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Confirm reset" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Shared demo progress has been reset.");
    expect(fetch).toHaveBeenCalledExactlyOnceWith("/api/progress/reset", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: "RESET DEMO PROGRESS" }),
    });
  });

  it.each([
    ["SESSION_ACTIVE", "Stop the active session"],
    ["STORAGE_UNAVAILABLE", "Progress could not be reset"],
  ])("shows %s without claiming success", async (code, message) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, json: async () => ({ error: { code } }) }));
    await open();
    fireEvent.click(screen.getByRole("button", { name: "Confirm reset" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
  });

  it("reports unknown network outcome without automatic retries", async () => {
    const fetch = vi.fn().mockRejectedValue(new Error("offline"));
    vi.stubGlobal("fetch", fetch);
    await open();
    fireEvent.click(screen.getByRole("button", { name: "Confirm reset" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("outcome is unknown");
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("disables confirmation while a reset is pending", async () => {
    let resolve!: (value: unknown) => void;
    const fetch = vi.fn().mockReturnValue(new Promise((done) => { resolve = done; }));
    vi.stubGlobal("fetch", fetch);
    await open();
    fireEvent.click(screen.getByRole("button", { name: "Confirm reset" }));
    expect(screen.getByRole("button", { name: "Resetting…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
    resolve({ ok: true, json: async () => ({ completed_challenge_ids: [] }) });
    await screen.findByRole("status");
  });
});

import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import App from "./App";

afterEach(cleanup);

beforeEach(() => window.history.replaceState(null, "", "/"));

describe("workstation", () => {
  it("browses Challenge briefings without replacing the workspace or starting an Attempt", async () => {
    render(<App />);
    expect(
      await screen.findByRole("heading", {
        name: "Hello, Satellite!",
        level: 1,
      }),
    ).toBeInTheDocument();
    const workspace = screen.getByRole("region", { name: "Workspace pane" });
    fireEvent.click(screen.getByRole("tab", { name: "Notes" }));
    fireEvent.click(screen.getByRole("link", { name: /Ready for the Pass/ }));
    expect(
      await screen.findByRole("heading", {
        name: "Ready for the Pass",
        level: 1,
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Workspace pane" })).toBe(
      workspace,
    );
    expect(screen.getByRole("tab", { name: "Notes" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByText("No active Attempt")).toBeInTheDocument();
    await act(async () => window.history.back());
    expect(
      await screen.findByRole("heading", {
        name: "Hello, Satellite!",
        level: 1,
      }),
    ).toBeInTheDocument();
    await act(async () => window.history.forward());
    expect(
      await screen.findByRole("heading", {
        name: "Ready for the Pass",
        level: 1,
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Workspace pane" })).toBe(
      workspace,
    );
    expect(screen.getByRole("tab", { name: "Notes" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(
      screen.queryByRole("button", { name: /Start|Switch/ }),
    ).not.toBeInTheDocument();
  });
  it("shows Not found for unknown Challenges and deferred tracks", () => {
    window.history.replaceState(null, "", "/challenges/offensive");
    render(<App />);
    expect(
      screen.getByRole("heading", { name: "Not found" }),
    ).toBeInTheDocument();
    expect(screen.getByText("No active Attempt")).toBeInTheDocument();
  });

  it("demonstrates persistent field errors and explicit confirmation in development", async () => {
    window.history.replaceState(null, "", "/dev/components");
    render(<App />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Submit example" }),
    );
    expect(
      screen.getByRole("textbox", { name: "Example filename" }),
    ).toHaveAttribute("aria-invalid", "true");
    fireEvent.change(
      screen.getByRole("textbox", { name: "Example filename" }),
      { target: { value: "notes.txt" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Submit example" }));
    expect(screen.getByRole("status")).toHaveTextContent(
      "Example submitted: notes.txt. Nothing was saved.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Reset example" }));
    expect(
      await screen.findByRole("alertdialog", { name: "Reset this example?" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(
      screen.getByRole("textbox", { name: "Example filename" }),
    ).toHaveValue("notes.txt");
    fireEvent.click(screen.getByRole("button", { name: "Reset example" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "Confirm example reset" }),
    );
    expect(
      screen.getByRole("textbox", { name: "Example filename" }),
    ).toHaveValue("");
    expect(screen.getByRole("status")).toHaveTextContent(
      "No Workspace was changed.",
    );
  });
});

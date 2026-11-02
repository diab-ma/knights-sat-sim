import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import TerminalPanel from "./TerminalPanel";

const terminalMock = vi.hoisted(() => ({
  options: undefined as Record<string, unknown> | undefined,
  inputHandler: undefined as ((data: string) => void) | undefined,
  write: vi.fn(),
  writeln: vi.fn(),
  dispose: vi.fn(),
  disposeInput: vi.fn(),
  fit: vi.fn(),
}));

vi.mock("@xterm/xterm", () => ({
  Terminal: class {
    constructor(options: Record<string, unknown>) {
      terminalMock.options = options;
    }

    loadAddon() {}
    open() {}

    write(data: string) {
      terminalMock.write(data);
    }

    writeln(data: string) {
      terminalMock.writeln(data);
    }

    onData(handler: (data: string) => void) {
      terminalMock.inputHandler = handler;
      return { dispose: terminalMock.disposeInput };
    }

    dispose() {
      terminalMock.dispose();
    }
  },
}));

vi.mock("@xterm/addon-fit", () => ({
  FitAddon: class {
    fit() {
      terminalMock.fit();
    }
  },
}));

afterEach(cleanup);

beforeEach(() => {
  vi.clearAllMocks();
  terminalMock.options = undefined;
  terminalMock.inputHandler = undefined;
});

describe("TerminalPanel", () => {
  it("starts xterm in local-echo mode with links and clipboard disabled", () => {
    render(<TerminalPanel />);

    expect(screen.getByRole("region", { name: "Terminal" })).toBeInTheDocument();
    expect(terminalMock.options).toMatchObject({
      allowProposedApi: false,
      linkHandler: null,
      rightClickSelectsWord: false,
    });
    expect(terminalMock.writeln).toHaveBeenCalledWith(
      "Hello from the terminal panel",
    );
    expect(terminalMock.write).toHaveBeenCalledWith("$ ");

    const terminal = screen.getByRole("region", { name: "Terminal" });
    const xtermHost = terminal.firstElementChild;
    expect(xtermHost).not.toBeNull();
    for (const type of ["copy", "cut", "paste"]) {
      const event = new Event(type, { bubbles: true, cancelable: true });
      xtermHost?.dispatchEvent(event);
      expect(event.defaultPrevented).toBe(true);
    }
  });

  it("echoes typed input, handles Enter and Backspace, then disposes xterm", () => {
    const { unmount } = render(<TerminalPanel />);
    const input = terminalMock.inputHandler;
    expect(input).toBeDefined();
    terminalMock.write.mockClear();

    input?.("h");
    input?.("e");
    input?.("\u007f");
    input?.("i");
    input?.("\r");

    expect(terminalMock.write.mock.calls).toEqual([
      ["h"],
      ["e"],
      ["\b \b"],
      ["i"],
      ["\r\n$ "],
    ]);

    unmount();
    expect(terminalMock.disposeInput).toHaveBeenCalledOnce();
    expect(terminalMock.dispose).toHaveBeenCalledOnce();
  });
});

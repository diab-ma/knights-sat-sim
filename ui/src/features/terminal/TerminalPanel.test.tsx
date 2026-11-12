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

const socketMock = vi.hoisted(() => ({
  instances: [] as Array<{
    url: string;
    readyState: number;
    binaryType: string;
    onmessage: ((event: MessageEvent) => void) | null;
    onerror: ((event: Event) => void) | null;
    onclose: ((event: CloseEvent) => void) | null;
    send: ReturnType<typeof vi.fn>;
    close: ReturnType<typeof vi.fn>;
  }>,
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

class MockWebSocket {
  static readonly OPEN = 1;

  readyState = 0;
  binaryType = "blob";
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  send = vi.fn();
  close = vi.fn(() => {
    this.readyState = 3;
    this.onclose?.({} as CloseEvent);
  });

  constructor(readonly url: string) {
    socketMock.instances.push(this);
  }
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

beforeEach(() => {
  vi.clearAllMocks();
  terminalMock.options = undefined;
  terminalMock.inputHandler = undefined;
  socketMock.instances = [];
  vi.stubGlobal("WebSocket", MockWebSocket);
});

describe("TerminalPanel", () => {
  it("starts xterm and opens the echo socket", () => {
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
    expect(socketMock.instances).toHaveLength(1);
    expect(socketMock.instances[0]).toMatchObject({
      url: "ws://localhost:8000/api/dev/echo",
      binaryType: "arraybuffer",
    });

    const terminal = screen.getByRole("region", { name: "Terminal" });
    const xtermHost = terminal.firstElementChild;
    expect(xtermHost).not.toBeNull();
    for (const type of ["copy", "cut", "paste"]) {
      const event = new Event(type, { bubbles: true, cancelable: true });
      xtermHost?.dispatchEvent(event);
      expect(event.defaultPrevented).toBe(false);
    }
  });

  it("sends input through the socket and writes server echoes", () => {
    const { unmount } = render(<TerminalPanel />);
    const input = terminalMock.inputHandler;
    const socket = socketMock.instances[0];
    expect(input).toBeDefined();
    socket.readyState = MockWebSocket.OPEN;
    terminalMock.write.mockClear();

    input?.("h");
    input?.("e");
    input?.("\u007f");
    input?.("i");
    input?.("\r");

    expect(socket.send.mock.calls).toEqual([
      ["h"],
      ["e"],
      ["\u007f"],
      ["i"],
      ["\r"],
    ]);
    for (const echoed of ["h", "e", "\u007f", "i", "\r"]) {
      const data = new ArrayBuffer(1);
      new Uint8Array(data)[0] = echoed.charCodeAt(0);
      socket.onmessage?.({ data } as MessageEvent);
    }

    expect(terminalMock.write.mock.calls).toEqual([
      [new Uint8Array([104])],
      [new Uint8Array([101])],
      [new Uint8Array([127])],
      [new Uint8Array([105])],
      [new Uint8Array([13])],
    ]);

    unmount();
    expect(terminalMock.disposeInput).toHaveBeenCalledOnce();
    expect(terminalMock.dispose).toHaveBeenCalledOnce();
    expect(socket.close).toHaveBeenCalledOnce();
  });

  it("reports a failed or closed connection only once", () => {
    render(<TerminalPanel />);
    const socket = socketMock.instances[0];

    socket.onerror?.(new Event("error"));
    socket.onclose?.({} as CloseEvent);

    expect(terminalMock.writeln).toHaveBeenCalledWith(
      "Not connected to the server",
    );
    expect(
      terminalMock.writeln.mock.calls.filter(
        ([message]) => message === "Not connected to the server",
      ),
    ).toHaveLength(1);
  });
});

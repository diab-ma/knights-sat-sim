import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./tabs";

afterEach(cleanup);

it.each([
  [undefined, "horizontal", "ArrowRight", "ArrowLeft", "ArrowDown"],
  ["vertical", "vertical", "ArrowDown", "ArrowUp", "ArrowRight"],
] as const)("aligns semantics and keyboard focus for orientation=%s", async (
  orientation,
  expected,
  next,
  previous,
  crossAxis,
) => {
  render(
    <Tabs orientation={orientation} defaultValue="first">
      <TabsList aria-label="Example tabs">
        <TabsTrigger value="first">First</TabsTrigger>
        <TabsTrigger value="second">Second</TabsTrigger>
      </TabsList>
      <TabsContent value="first">First panel</TabsContent>
      <TabsContent value="second">Second panel</TabsContent>
    </Tabs>,
  );
  const list = screen.getByRole("tablist");
  expect(list.getAttribute("aria-orientation") ?? "horizontal").toBe(expected);
  const first = screen.getByRole("tab", { name: "First" });
  const second = screen.getByRole("tab", { name: "Second" });
  act(() => first.focus());
  fireEvent.keyDown(first, { key: crossAxis });
  expect(first).toHaveFocus();
  fireEvent.keyDown(first, { key: next });
  await waitFor(() => expect(second).toHaveFocus());
  expect(first).toHaveAttribute("aria-selected", "true");
  fireEvent.keyDown(second, { key: previous });
  await waitFor(() => expect(first).toHaveFocus());
});

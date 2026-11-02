import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import fixture from "../test/fixture.json";
import { App } from "./App";

const ok = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("App", () => {
  it("shows a skeleton while loading, then the experiments", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => ok(fixture));
    render(<App url="/data/results.json" />);
    expect(screen.getAllByRole("status").length).toBeGreaterThan(0);
    expect(await screen.findByText(/interval holds it|intervals of the/)).toBeTruthy();
    expect(screen.getByTestId("design-budget_split")).toBeTruthy();
    expect(screen.getByTestId("policy-balanced")).toBeTruthy();
    expect(screen.getByTestId("model-contact")).toBeTruthy();
  });

  it("shows an empty state when the held-out markets have not run", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => ok(fixture));
    render(<App url="/data/results.json" />);
    expect(await screen.findByText("The held-out markets have not been run")).toBeTruthy();
  });

  it("explains a failure and retries", async () => {
    const f = vi
      .spyOn(globalThis, "fetch")
      .mockImplementationOnce(() => Promise.resolve(new Response("nope", { status: 404 })))
      .mockImplementation(() => ok(fixture));
    render(<App url="/data/results.json" />);
    const alerts = await screen.findAllByRole("alert");
    expect(alerts[0].textContent).toMatch(/404/);
    fireEvent.click(within(alerts[0]).getByRole("button", { name: "Try again" }));
    expect(await screen.findByTestId("design-budget_split")).toBeTruthy();
    expect(f).toHaveBeenCalledTimes(2);
  });

  it("rejects a file in the wrong format", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => ok({ hello: 1 }));
    render(<App url="/data/results.json" />);
    expect((await screen.findAllByRole("alert"))[0].textContent).toMatch(/not in the format/);
  });

  it("switches the outcome", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => ok(fixture));
    render(<App url="/data/results.json" />);
    const group = await screen.findByRole("group", { name: "Outcome" });
    fireEvent.click(within(group).getByRole("radio", { name: "Revenue" }));
    expect((within(group).getByRole("radio", { name: "Revenue" }) as HTMLInputElement).checked).toBe(true);
    expect(screen.getByText(/model changes lead revenue per request by/)).toBeTruthy();
  });
});

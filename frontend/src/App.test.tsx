import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { App } from "./App";
import { renderWithQueries } from "./test/render";
import { server } from "./test/server";

describe("App", () => {
  it("answers the headline question from the summary", async () => {
    renderWithQueries(<App />);
    expect(await screen.findByText("3.8%")).toBeInTheDocument();
    expect(screen.getByText(/8,161 subway delays/)).toBeInTheDocument();
  });

  it("labels every station with its delay count, not only with colour", async () => {
    renderWithQueries(<App />);
    expect(
      await screen.findByRole("button", { name: "Union: 40 delays of 5+ minutes" }),
    ).toBeInTheDocument();
  });

  it("opens a station from the map with the keyboard and keeps it in the URL", async () => {
    const user = userEvent.setup();
    renderWithQueries(<App />);

    const union = await screen.findByRole("button", { name: /^Union:/ });
    union.focus();
    await user.keyboard("{Enter}");

    const panel = await screen.findByRole("complementary", { name: "Union" });
    expect(within(panel).getByText("140")).toBeInTheDocument();
    expect(within(panel).getByText("Disorderly Patron")).toBeInTheDocument();
    expect(within(panel).getByText("signal failure")).toBeInTheDocument();
    expect(within(panel).getByText(/Code TUNCA \(not in the TTC's published list\)/)).toBeVisible();
    expect(union).toHaveAttribute("aria-pressed", "true");
    expect(window.location.search).toBe("?station=union");
  });

  it("opens the station from a shared link", async () => {
    window.history.replaceState(null, "", "/?station=union");
    renderWithQueries(<App />);
    expect(await screen.findByRole("complementary", { name: "Union" })).toBeInTheDocument();
  });

  it("explains a commute's risk and highlights its stations", async () => {
    const user = userEvent.setup();
    renderWithQueries(<App />);

    await user.selectOptions(await screen.findByLabelText("Day"), "Friday");
    await user.click(screen.getByRole("button", { name: "Check" }));

    expect(await screen.findByText("28%")).toBeInTheDocument();
    expect(
      screen.getByText(/On 24 of 87 Fridays, a delay of 5\+ minutes hit Bloor-Yonge → Union/),
    ).toBeInTheDocument();
    expect(screen.getByText(/between 08:00 and 08:34/)).toBeInTheDocument();
    const kipling = screen.getByRole("button", { name: /^Kipling:/ });
    expect(kipling).toHaveAttribute("data-dimmed", "true");
  });

  it("resets the trip when the line changes", async () => {
    const user = userEvent.setup();
    renderWithQueries(<App />);
    await user.click(await screen.findByRole("button", { name: "Check" }));
    await screen.findByText("28%");

    await user.selectOptions(screen.getByLabelText("Line"), "4");

    expect(screen.queryByText("28%")).not.toBeInTheDocument();
    expect(screen.getByLabelText("From")).toHaveValue("sheppard-yonge");
    expect(screen.getByLabelText("To")).toHaveValue("don-mills");
  });

  it("tells the user when the API is down", async () => {
    server.use(http.get("*/api/lines", () => HttpResponse.json({}, { status: 503 })));
    renderWithQueries(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't load the subway lines.");
  });

  it("tells the user when a station can't be loaded", async () => {
    window.history.replaceState(null, "", "/?station=leaside");
    renderWithQueries(<App />);
    expect(await screen.findByText(/Couldn't load this station/)).toBeInTheDocument();
  });

  it("tells the user when the commute check fails", async () => {
    server.use(http.post("*/api/commute/risk", () => HttpResponse.json({}, { status: 500 })));
    const user = userEvent.setup();
    renderWithQueries(<App />);
    await user.click(await screen.findByRole("button", { name: "Check" }));
    expect(await screen.findByText(/Couldn't check that trip/)).toBeInTheDocument();
  });
});

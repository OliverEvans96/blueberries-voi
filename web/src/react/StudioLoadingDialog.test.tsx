// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it } from "vitest";
import { StudioLoadingDialog } from "./StudioLoadingDialog";

describe("StudioLoadingDialog (T-149)", () => {
  it("renders nothing when not visible", () => {
    const host = document.createElement("div");
    host.id = "studio-loading-host";
    document.body.appendChild(host);

    render(
      createElement(StudioLoadingDialog, {
        visible: false,
        message: "Advancing…",
        portalContainerRef: { current: host },
      }),
    );

    expect(screen.queryByRole("status")).toBeNull();
    expect(host.querySelector("dialog")).toBeNull();
  });

  it("shows message when visible", () => {
    const host = document.createElement("div");
    host.id = "studio-loading-host";
    document.body.appendChild(host);

    render(
      createElement(StudioLoadingDialog, {
        visible: true,
        message: "Updating observations…",
        portalContainerRef: { current: host },
      }),
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "Updating observations…",
    );
    expect(host.querySelector("dialog.studio-loading-dialog")).not.toBeNull();
  });

  it("uses default host when portal ref is omitted", () => {
    const host = document.createElement("div");
    host.id = "studio-loading-host";
    document.body.appendChild(host);

    render(
      createElement(StudioLoadingDialog, {
        visible: true,
        message: "Advancing…",
      }),
    );

    expect(screen.getByRole("status")).toHaveTextContent("Advancing…");
  });

  it("renders pulsing status dot", () => {
    const host = document.createElement("div");
    host.id = "studio-loading-host";
    document.body.appendChild(host);

    render(
      createElement(StudioLoadingDialog, {
        visible: true,
        message: "Advancing…",
        portalContainerRef: { current: host },
      }),
    );

    expect(
      host.querySelector(".studio-loading-dialog-dot.engine-status-dot"),
    ).not.toBeNull();
  });
});

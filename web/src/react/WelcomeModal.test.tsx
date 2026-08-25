// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { WelcomeModal } from "./WelcomeModal";

function makeHost(): HTMLElement {
  const host = document.createElement("div");
  document.body.appendChild(host);
  return host;
}

describe("WelcomeModal", () => {
  it("renders nothing visible when not open", () => {
    const host = makeHost();

    render(
      createElement(WelcomeModal, {
        open: false,
        onDismiss: () => undefined,
        portalContainerRef: { current: host },
      }),
    );

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(host.querySelector("dialog")).toBeNull();
  });

  it("shows a warm introduction when open", () => {
    const host = makeHost();

    render(
      createElement(WelcomeModal, {
        open: true,
        onDismiss: () => undefined,
        portalContainerRef: { current: host },
      }),
    );

    const dialog = host.querySelector("dialog.welcome-modal");
    expect(dialog).not.toBeNull();
    expect(dialog).toHaveTextContent("Welcome to Blueberry Aisle");
    expect(dialog).toHaveTextContent("store manager");
  });

  it("introduces the model, filter, and controller in plain terms", () => {
    const host = makeHost();

    render(
      createElement(WelcomeModal, {
        open: true,
        onDismiss: () => undefined,
        portalContainerRef: { current: host },
      }),
    );

    expect(host).toHaveTextContent("The model");
    expect(host).toHaveTextContent("The filter");
    expect(host).toHaveTextContent("The controller");
    expect(host).toHaveTextContent("A hidden shelf of blueberries");
    expect(host).toHaveTextContent(/produce manager/i);
    expect(host).toHaveTextContent(/Autopilot mode/i);
  });

  it("shows green step circles inline with labels, body full-width below", () => {
    const host = makeHost();

    render(
      createElement(WelcomeModal, {
        open: true,
        onDismiss: () => undefined,
        portalContainerRef: { current: host },
      }),
    );

    const indices = host.querySelectorAll(".welcome-modal-step-index");
    expect(indices).toHaveLength(3);
    expect(indices[0]?.textContent).toBe("1");
    expect(host.querySelector(".welcome-modal-step-copy")).toBeNull();
  });

  it("calls onDismiss when the close button is clicked", () => {
    const host = makeHost();
    const onDismiss = vi.fn();

    render(
      createElement(WelcomeModal, {
        open: true,
        onDismiss,
        portalContainerRef: { current: host },
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: "Close welcome" }));
    expect(onDismiss).toHaveBeenCalled();
  });

  it("calls onDismiss when the Start exploring button is clicked", () => {
    const host = makeHost();
    const onDismiss = vi.fn();

    render(
      createElement(WelcomeModal, {
        open: true,
        onDismiss,
        portalContainerRef: { current: host },
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: "Start exploring" }));
    expect(onDismiss).toHaveBeenCalled();
  });

  it("without a portal ref, portals into the nearest .bv-studio scope root", () => {
    const scope = document.createElement("div");
    scope.className = "bv-studio";
    document.body.appendChild(scope);

    render(
      createElement(WelcomeModal, { open: true, onDismiss: () => undefined }),
      { container: scope },
    );

    const dialog = scope.querySelector("dialog.welcome-modal");
    expect(dialog).not.toBeNull();
  });

  it("without a portal ref or .bv-studio ancestor, falls back to document.body", () => {
    render(
      createElement(WelcomeModal, { open: true, onDismiss: () => undefined }),
    );

    expect(screen.getByText("Start exploring")).toBeInTheDocument();
  });
});

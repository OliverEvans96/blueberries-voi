import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  STUDIO_LOADING_DELAY_MS,
  createDelayedLoadingHandle,
} from "./delayedLoading";

describe("createDelayedLoadingHandle (T-149)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("exports 750ms default delay", () => {
    expect(STUDIO_LOADING_DELAY_MS).toBe(750);
  });

  it("does not show for fast operations", () => {
    const onVisibleChange = vi.fn();
    const handle = createDelayedLoadingHandle(onVisibleChange, 750);

    handle.begin();
    vi.advanceTimersByTime(749);
    expect(onVisibleChange).not.toHaveBeenCalled();

    handle.end();
    vi.advanceTimersByTime(10);
    expect(onVisibleChange).not.toHaveBeenCalled();
  });

  it("shows after delay when operation is still running", () => {
    const onVisibleChange = vi.fn();
    const handle = createDelayedLoadingHandle(onVisibleChange, 750);

    handle.begin();
    vi.advanceTimersByTime(750);
    expect(onVisibleChange).toHaveBeenCalledWith(true);

    handle.end();
    expect(onVisibleChange).toHaveBeenLastCalledWith(false);
  });

  it("hides immediately when slow operation completes", () => {
    const onVisibleChange = vi.fn();
    const handle = createDelayedLoadingHandle(onVisibleChange, 750);

    handle.begin();
    vi.advanceTimersByTime(750);
    expect(onVisibleChange).toHaveBeenCalledWith(true);

    handle.end();
    expect(onVisibleChange).toHaveBeenLastCalledWith(false);
    expect(onVisibleChange).toHaveBeenCalledTimes(2);
  });

  it("ref-count keeps dialog visible until last end", () => {
    const onVisibleChange = vi.fn();
    const handle = createDelayedLoadingHandle(onVisibleChange, 750);

    handle.begin();
    handle.begin();
    vi.advanceTimersByTime(750);
    expect(onVisibleChange).toHaveBeenCalledWith(true);

    handle.end();
    expect(onVisibleChange).toHaveBeenLastCalledWith(true);

    handle.end();
    expect(onVisibleChange).toHaveBeenLastCalledWith(false);
  });

  it("clears pending timer when fast nested ops complete", () => {
    const onVisibleChange = vi.fn();
    const handle = createDelayedLoadingHandle(onVisibleChange, 750);

    handle.begin();
    handle.begin();
    handle.end();
    handle.end();
    vi.advanceTimersByTime(750);
    expect(onVisibleChange).not.toHaveBeenCalled();
  });

  it("end is a no-op when ref-count is already zero", () => {
    const onVisibleChange = vi.fn();
    const handle = createDelayedLoadingHandle(onVisibleChange, 750);

    handle.end();
    expect(onVisibleChange).not.toHaveBeenCalled();
  });
});

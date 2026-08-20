/**
 * WasmAdapter — VITE_ENGINE_ADAPTER=wasm (ADR 0120).
 * Module worker + JSON RPC only (no main-thread physics).
 */

import type { EngineAdapter } from "./adapter";
import { toFlatActParams } from "./actOpts";
import type { ActOpts, DayDelta, EngineConfig, EventsResult, Snapshot, TradeoffForecastResult } from "./types";

export type WasmAdapterOpts = {
  workerUrl: string;
  pkgUrl?: string;
};

type RpcRequest = { id: string; method: string; params?: Record<string, unknown> };
type RpcOk = { id: string; ok: true; result: unknown };
type RpcErr = { id: string; ok: false; error: { type?: string; message?: string } };
type RpcResponse = RpcOk | RpcErr;

export class WasmAdapter implements EngineAdapter {
  private readonly worker: Worker;
  private nextId = 0;
  private readonly pending = new Map<
    string,
    { resolve: (v: unknown) => void; reject: (e: Error) => void }
  >();
  private readonly onMessage: (ev: MessageEvent) => void;
  private readonly onError: (ev: ErrorEvent) => void;

  constructor(opts: WasmAdapterOpts) {
    const sep = opts.workerUrl.includes("?") ? "&" : "?";
    const url = opts.pkgUrl
      ? `${opts.workerUrl}${sep}pkgUrl=${encodeURIComponent(opts.pkgUrl)}`
      : opts.workerUrl;
    this.worker = new Worker(url, { type: "module" });
    this.onMessage = (ev: MessageEvent) => {
      let resp: RpcResponse;
      try {
        const raw = ev.data;
        resp =
          typeof raw === "string" ? (JSON.parse(raw) as RpcResponse) : (raw as RpcResponse);
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        for (const [, waiter] of this.pending) {
          waiter.reject(new Error(`RPC response parse failed: ${message}`));
        }
        this.pending.clear();
        return;
      }
      const id = resp.id != null ? String(resp.id) : "";
      const waiter = this.pending.get(id);
      if (!waiter) return;
      this.pending.delete(id);
      if (!resp.ok) {
        const err = resp.error ?? {};
        waiter.reject(new Error(`${err.type ?? "RpcError"}: ${err.message ?? "unknown"}`));
        return;
      }
      waiter.resolve(resp.result);
    };
    this.onError = (ev: ErrorEvent) => {
      const message = ev.message || "Worker error";
      for (const [, waiter] of this.pending) {
        waiter.reject(new Error(message));
      }
      this.pending.clear();
    };
    this.worker.addEventListener("message", this.onMessage);
    this.worker.addEventListener("error", this.onError);
  }

  private call(method: string, params: Record<string, unknown> = {}): Promise<unknown> {
    const id = `rpc-${++this.nextId}`;
    const request: RpcRequest = { id, method, params };
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.worker.postMessage(JSON.stringify(request));
    });
  }

  async init(config?: EngineConfig): Promise<Snapshot> {
    return (await this.call("init", { config: config ?? {} })) as Snapshot;
  }

  async step(order_qty: number): Promise<DayDelta> {
    return (await this.call("step", { order: order_qty, order_qty })) as DayDelta;
  }

  async step_n(orders: number[]): Promise<DayDelta[]> {
    return (await this.call("step_n", { orders })) as DayDelta[];
  }

  async reset(config?: EngineConfig): Promise<Snapshot> {
    return (await this.call("reset", { config: config ?? {} })) as Snapshot;
  }

  async act(opts?: ActOpts): Promise<DayDelta> {
    return (await this.call("act", toFlatActParams(opts))) as DayDelta;
  }

  async setObsScenario(obs_scenario: string): Promise<Snapshot> {
    return (await this.call("set_obs_scenario", { obs_scenario })) as Snapshot;
  }

  async set_obs_scenario(obs_scenario: string): Promise<Snapshot> {
    return this.setObsScenario(obs_scenario);
  }

  async setObsChannels(channels: {
    code_type: string;
    scan_waste: boolean;
    delivery_history: string;
  }): Promise<Snapshot> {
    return (await this.call("set_obs_channels", channels)) as Snapshot;
  }

  async set_obs_channels(channels: {
    code_type: string;
    scan_waste: boolean;
    delivery_history: string;
  }): Promise<Snapshot> {
    return this.setObsChannels(channels);
  }

  async tradeoffForecast(params?: {
    n_paths?: number;
    protection_days?: number;
  }): Promise<TradeoffForecastResult> {
    return (await this.call("tradeoff_forecast", params ?? {})) as TradeoffForecastResult;
  }

  async events(params: { since_day: number }): Promise<EventsResult> {
    return (await this.call("events", params)) as EventsResult;
  }

  terminate(): void {
    this.worker.removeEventListener("message", this.onMessage);
    this.worker.removeEventListener("error", this.onError);
    this.worker.terminate();
    this.pending.clear();
  }
}

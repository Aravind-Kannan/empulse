/** Tracks production cold-start warmup — decoupled from api-client to avoid import cycles. */

let warming = false;

export function setBackendWarming(value: boolean) {
  warming = value;
}

export function isBackendWarmupActive(): boolean {
  return warming;
}

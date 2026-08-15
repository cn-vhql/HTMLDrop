import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";

// jsdom 无 canvas 实现，qrcode 的 toCanvas 需要 mock
vi.mock("qrcode", () => ({ default: { toCanvas: vi.fn() } }));

afterEach(() => {
  document.body.innerHTML = "";
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  localStorage.clear();
});

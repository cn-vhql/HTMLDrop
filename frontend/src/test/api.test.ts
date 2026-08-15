import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, setApiToken } from "../api";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

describe("api client", () => {
  beforeEach(() => {
    setApiToken(null);
    vi.restoreAllMocks();
  });

  it("注入 X-API-Token 请求头", async () => {
    setApiToken("tok-123");
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await api("/api/links");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/links");
    expect(new Headers(init.headers).get("X-API-Token")).toBe("tok-123");
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer tok-123");
  });

  it("未设置令牌时不带 X-API-Token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}));
    vi.stubGlobal("fetch", fetchMock);
    await api("/api/links");
    const [, init] = fetchMock.mock.calls[0];
    expect(new Headers(init.headers).get("X-API-Token")).toBeNull();
  });

  it("始终携带 credentials include", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}));
    vi.stubGlobal("fetch", fetchMock);
    await api("/api/links");
    expect(fetchMock.mock.calls[0][1].credentials).toBe("include");
  });

  it("业务错误时抛出后端 detail 信息", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detail: "请先登录" }, 401));
    vi.stubGlobal("fetch", fetchMock);
    await expect(api("/api/auth/me")).rejects.toThrow("请先登录");
  });

  it("非 JSON 错误时使用兜底文案", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("boom", { status: 500 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(api("/api/links")).rejects.toThrow("请求失败，请稍后重试");
  });

  it("成功时返回解析后的 JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ items: [1, 2] }));
    vi.stubGlobal("fetch", fetchMock);
    const data = await api<{ items: number[] }>("/api/links");
    expect(data.items).toEqual([1, 2]);
  });
});

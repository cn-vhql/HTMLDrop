import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import App from "../App";
import { setApiToken } from "../api";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

type Handler = (init?: RequestInit) => Response;

function installFetch(routes: Record<string, Handler>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    const key = `${method} ${url}`;
    const exact = routes[key] ?? routes[url];
    if (exact) return exact(init);
    // 支持带 query 的 URL 前缀匹配
    const matched = Object.entries(routes).find(([routeKey]) => key.startsWith(routeKey) || url.startsWith(routeKey));
    if (matched) return matched[1](init);
    throw new Error(`unmocked fetch: ${key}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function makeLink(id: number, name = `页面${id}`) {
  return {
    id, slug: `slug${id}`, name, description: "", source_type: "html" as const,
    status: "active" as const, view_count: id * 10, created_at: "2026-08-01 10:00:00",
    updated_at: "2026-08-15 10:00:00", password_protected: false, url: `http://test/p/slug${id}`,
  };
}

const links = Array.from({ length: 8 }, (_, i) => makeLink(i + 1));

function dashboardRoutes() {
  return {
    "GET /api/auth/me": () => jsonResponse({ detail: "请先登录" }, 401),
    "GET /api/links": () => jsonResponse({ items: links, total: 20, page: 1, page_size: 8 }),
    "GET /api/links/summary": () => jsonResponse({ total: 20, total_views: 880, active: 18 }),
    "GET /api/health": () => jsonResponse({ status: "ok" }),
  };
}

async function login(user = userEvent.setup()) {
  installFetch({
    "POST /api/auth/login": () => jsonResponse({ username: "admin", api_token: "tok-abc", default_password: true }),
    "POST /api/auth/logout": () => jsonResponse({ ok: true }),
    ...dashboardRoutes(),
  });
  render(<App />);
  await user.click(await screen.findByRole("button", { name: /进入管理台/ }));
  return user;
}

describe("App", () => {
  it("未登录时显示登录页", async () => {
    installFetch({ "GET /api/auth/me": () => jsonResponse({ detail: "请先登录" }, 401) });
    render(<App />);
    expect(await screen.findByText("登录管理台")).toBeInTheDocument();
  });

  it("登录后进入 Dashboard 并显示统计与发布面板", async () => {
    await login();
    expect(await screen.findByText("页面发布")).toBeInTheDocument();
    expect(await screen.findByText("页面总数")).toBeInTheDocument();
    expect((await screen.findAllByText("20")).length).toBeGreaterThan(0);
    expect(await screen.findByText("发布一个新页面")).toBeInTheDocument();
    // 默认密码提醒横幅
    expect(await screen.findByText(/默认密码/)).toBeInTheDocument();
  });

  it("切换到全部页面显示列表与分页控件", async () => {
    await login();
    await (await screen.findByRole("button", { name: /全部页面/ })).click();
    expect((await screen.findAllByText("我的页面")).length).toBeGreaterThan(0);
    expect(await screen.findByText("页面1")).toBeInTheDocument();
    // 页码按钮与总数
    expect(await screen.findByRole("button", { name: "1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "2" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "3" })).toBeInTheDocument();
    expect(screen.getByText("共 20 条")).toBeInTheDocument();
  });

  it("点击页码按钮发起对应分页请求", async () => {
    await login();
    await (await screen.findByRole("button", { name: /全部页面/ })).click();
    await screen.findByRole("button", { name: "2" });
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/links?page=2")) return jsonResponse({ items: links, total: 20, page: 2, page_size: 8 });
      if (url.includes("/api/links/summary") || url.includes("/api/health")) return jsonResponse({ total: 20, total_views: 880, active: 18 });
      throw new Error(`unmocked ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    await userEvent.setup().click(screen.getByRole("button", { name: "2" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("page=2"), expect.anything()));
  });

  it("点击更多按钮弹出操作菜单", async () => {
    await login();
    await (await screen.findByRole("button", { name: /全部页面/ })).click();
    const moreButtons = await screen.findAllByRole("button", { name: "更多操作" });
    await userEvent.setup().click(moreButtons[0]);
    expect(await screen.findByRole("menuitem", { name: "查看统计" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "编辑" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "停止访问" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "删除" })).toBeInTheDocument();
  });

  it("点击行内二维码按钮弹出二维码弹窗", async () => {
    await login();
    await (await screen.findByRole("button", { name: /全部页面/ })).click();
    const qrButtons = await screen.findAllByRole("button", { name: "查看二维码" });
    await userEvent.setup().click(qrButtons[0]);
    const dialog = await screen.findByRole("dialog", { name: "页面二维码" });
    expect(dialog).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "下载二维码" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "复制链接" })).toBeInTheDocument();
    // 弹窗显示对应链接
    expect(within(dialog).getByText("http://test/p/slug1")).toBeInTheDocument();
  });

  it("顶部已移除发布按钮，服务状态显示正常", async () => {
    await login();
    expect(await screen.findByText("服务运行正常")).toBeInTheDocument();
    // topbar 不再有单独的“发布”按钮（“立即发布/去发布”属于发布面板与空状态）
    expect(screen.queryByRole("button", { name: /^发布$/ })).not.toBeInTheDocument();
  });

  it("登出后回到登录页", async () => {
    const user = await login();
    await user.click(screen.getByRole("button", { name: "退出登录" }));
    expect(await screen.findByText("登录管理台")).toBeInTheDocument();
    setApiToken(null);
  });

  it("左下角修改密码流程", async () => {
    const user = await login();
    await user.click(screen.getByRole("button", { name: "修改密码" }));
    expect(await screen.findByRole("dialog", { name: "修改密码" })).toBeInTheDocument();
    // 两次密码不一致 -> 前端拦截
    await user.type(screen.getByLabelText("当前密码"), "admin123");
    await user.type(screen.getByLabelText(/^新密码/), "newpass123");
    await user.type(screen.getByLabelText("确认新密码"), "different");
    await user.click(screen.getByRole("button", { name: "确认修改" }));
    expect(await screen.findByText("两次输入的新密码不一致")).toBeInTheDocument();
    // 修正后提交成功
    installFetch({ "POST /api/auth/password": () => jsonResponse({ ok: true }) });
    const confirmInput = screen.getByLabelText("确认新密码");
    await user.clear(confirmInput);
    await user.type(confirmInput, "newpass123");
    await user.click(screen.getByRole("button", { name: "确认修改" }));
    expect(await screen.findByText("密码已修改")).toBeInTheDocument();
    expect(screen.queryByText(/默认密码/)).not.toBeInTheDocument();
    setApiToken(null);
  });

  it("加载失败显示错误横幅", async () => {
    await login();
    installFetch({
      "GET /api/links": () => jsonResponse({ detail: "服务器开小差了" }, 500),
      "GET /api/links/summary": () => jsonResponse({ total: 0, total_views: 0, active: 0 }),
      "GET /api/health": () => jsonResponse({ status: "ok" }),
    });
    await (await screen.findByRole("button", { name: "刷新" })).click();
    expect(await screen.findByText("服务器开小差了")).toBeInTheDocument();
  });
});

export type LinkItem = {
  id: number;
  slug: string;
  name: string;
  description: string;
  source_type: "html" | "zip";
  status: "active" | "stopped" | "deleted";
  view_count: number;
  created_at: string;
  updated_at: string;
  password_protected: boolean;
  url: string;
};

export type LinkListResponse = {
  items: LinkItem[];
  total: number;
  page: number;
  page_size: number;
};

export type Stats = {
  view_count: number;
  uv: number;
  total_uv: number;
  peak: { day: string; pv: number } | null;
  daily: { day: string; pv: number; uv: number }[];
  hourly: { hour: string; pv: number; uv: number }[];
  browsers: { name: string; value: number }[];
  devices: { name: string; value: number }[];
  os: { name: string; value: number }[];
  referers: { name: string; value: number }[];
  recent: { visited_at: string; browser: string; os: string; device: string; referer: string }[];
};

// 管理 API 令牌：只保存在 JS 内存中，不落 localStorage/sessionStorage，
// 避免同源发布页（/p/*）读取后冒充管理台调用 API。
let apiToken: string | null = null;

export function setApiToken(token: string | null) {
  apiToken = token;
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (apiToken) headers.set("X-API-Token", apiToken);
  const response = await fetch(path, { ...options, headers, credentials: "include" });
  const contentType = response.headers.get("content-type") ?? "";
  const body = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) throw new Error(body?.detail || "请求失败，请稍后重试");
  return body as T;
}

export function formData(values: Record<string, string | File>): FormData {
  const data = new FormData();
  Object.entries(values).forEach(([key, value]) => data.append(key, value));
  return data;
}

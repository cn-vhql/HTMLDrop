import { useEffect, useMemo, useRef, useState } from "react";
import type { DragEvent, FormEvent, ReactNode } from "react";
import QRCode from "qrcode";
import {
  Activity, Archive, BarChart3, Check, Clipboard, ExternalLink, FileArchive,
  FileCode2, FileUp, KeyRound, LayoutDashboard, Lock, LogOut, MoreHorizontal, Pause, Pencil,
  Play, Plus, QrCode, RefreshCw, Search, Trash2, UploadCloud, X,
} from "lucide-react";
import { api, formData, setApiToken, LinkItem, LinkListResponse, Stats } from "./api";

type User = { username: string; default_password?: boolean };

/** 弹窗通用行为：Esc 关闭、点击遮罩关闭、锁定背景滚动、聚焦弹窗并在关闭后还原焦点 */
function useDialog(onClose: () => void) {
  const ref = useRef<HTMLDivElement | null>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onCloseRef.current(); };
    document.addEventListener("keydown", onKey);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
      previous?.focus?.();
    };
  }, []);
  return ref;
}

function formatDate(value: string) {
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value.replace(" ", "T")}Z`;
  return new Date(normalized).toLocaleString("zh-CN", { hour12: false, timeZone: "Asia/Shanghai" });
}

/** 品牌标志 SVG（组件与二维码中心共用同一份设计） */
const BRAND_LOGO_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 28"><rect width="28" height="28" rx="7.5" fill="#bde7d8"/><path d="M9.2 6.6h6.2l3.4 3.4v11.2c0 .6-.5 1.1-1.1 1.1H9.2c-.6 0-1.1-.5-1.1-1.1V7.7c0-.6.5-1.1 1.1-1.1z" fill="#12403a"/><path d="M15.4 6.6v3.4h3.4" fill="none" stroke="#12403a" stroke-width="1.3"/><polyline points="10.4,15.6 9,17.3 10.4,19" fill="none" stroke="#c9f0e2" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><line x1="11.9" y1="19.4" x2="15.6" y2="15.2" stroke="#c9f0e2" stroke-width="1.5" stroke-linecap="round"/><polyline points="17.1,15.6 18.5,17.3 17.1,19" fill="none" stroke="#c9f0e2" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><circle cx="21.4" cy="6.8" r="1.4" fill="#f2b85c"/></svg>`;

/** 生成带品牌 logo 的二维码（绘制到 canvas 中心） */
function drawQrWithLogo(canvas: HTMLCanvasElement, text: string) {
  QRCode.toCanvas(canvas, text, { width: 200, margin: 1, errorCorrectionLevel: "H", color: { dark: "#173334", light: "#ffffff" } }, () => {
    const img = new Image();
    img.onload = () => {
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      const size = canvas.width * 0.26;
      const x = (canvas.width - size) / 2;
      const y = (canvas.height - size) / 2;
      const pad = size * 0.12;
      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.roundRect(x - pad, y - pad, size + pad * 2, size + pad * 2, size * 0.18);
      ctx.fill();
      ctx.drawImage(img, x, y, size, size);
    };
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(BRAND_LOGO_SVG);
  });
}

/** 品牌标志：页面卡片 + </> + 金色发布圆点 */
function BrandLogo() {
  return <span className="brand-logo" role="img" aria-label="HTML Drop 标志" dangerouslySetInnerHTML={{ __html: BRAND_LOGO_SVG }} />;
}

function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault(); setError(""); setLoading(true);
    try {
      const user = await api<User & { api_token: string }>("/api/auth/login", { method: "POST", body: formData({ username, password }) });
      setApiToken(user.api_token);
      onLogin(user);
    } catch (err) { setError(err instanceof Error ? err.message : "登录失败"); }
    finally { setLoading(false); }
  }

  return <main className="login-shell">
    <section className="login-art">
      <div className="brand-mark"><BrandLogo /> HTML Drop</div>
      <div className="login-art-copy"><p className="eyebrow">PERSONAL PUBLISHING SPACE</p><h1>把页面，<br /><em>变成链接。</em></h1><p>轻量发布你的 HTML 页面和静态站点，随时查看访问表现。</p></div>
      <div className="art-footer"><span>LOCAL-FIRST</span><span>v1.0</span></div>
    </section>
    <section className="login-panel"><div className="login-card">
      <div className="mobile-brand"><BrandLogo /> HTML Drop</div>
      <p className="eyebrow">WELCOME BACK</p><h2>登录管理台</h2><p className="muted">管理你发布的页面与访问数据。</p>
      <form onSubmit={submit} className="login-form">
        <label>用户名<input value={username} onChange={e => setUsername(e.target.value)} autoComplete="username" required /></label>
        <label>密码<input value={password} onChange={e => setPassword(e.target.value)} type="password" autoComplete="current-password" required /></label>
        {error && <div className="error-text">{error}</div>}
        <button className="primary-button full" disabled={loading}>{loading ? "登录中..." : "进入管理台"}<ExternalLink size={16} /></button>
      </form>
      <p className="login-hint">首次运行默认账号：admin<br />默认密码：admin123</p>
    </div></section>
  </main>;
}

function UploadPanel({ onCreated }: { onCreated: (link: LinkItem) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const dragDepth = useRef(0);

  async function submit(event: FormEvent) {
    event.preventDefault(); if (!file) { setError("请选择 HTML 或 ZIP 文件"); return; }
    setError(""); setLoading(true);
    try {
      const link = await api<LinkItem>("/api/links", { method: "POST", body: formData({ file, name, description, password }) });
      setFile(null); setName(""); setDescription(""); setPassword(""); (document.getElementById("upload-file") as HTMLInputElement).value = ""; onCreated(link);
    } catch (err) { setError(err instanceof Error ? err.message : "上传失败"); }
    finally { setLoading(false); }
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    dragDepth.current = 0; setDragging(false);
    const dropped = event.dataTransfer.files?.[0];
    if (!dropped) return;
    const suffix = dropped.name.split(".").pop()?.toLowerCase() ?? "";
    if (!["html", "htm", "zip"].includes(suffix)) { setError("仅支持 HTML 或 ZIP 文件"); return; }
    setError(""); setFile(dropped);
  }

  return <section className="publish-panel">
    <div className="section-heading"><div><p className="eyebrow">NEW PUBLICATION</p><h2>发布一个新页面</h2></div><div className="format-badges"><span><FileCode2 size={14} /> HTML</span><span><FileArchive size={14} /> ZIP</span></div></div>
    <form onSubmit={submit} className="publish-form">
      <label className={`file-picker ${dragging ? "dragging" : ""}`} htmlFor="upload-file" onDragEnter={e => { e.preventDefault(); dragDepth.current += 1; setDragging(true); }} onDragOver={e => e.preventDefault()} onDragLeave={() => { dragDepth.current = Math.max(0, dragDepth.current - 1); if (dragDepth.current === 0) setDragging(false); }} onDrop={onDrop}><UploadCloud size={24} /><span>{file ? file.name : "点击选择或拖拽文件到此处"}</span><small>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : "单文件最大 50 MB，ZIP 需包含 index.html"}</small><input id="upload-file" type="file" accept=".html,.htm,.zip" onChange={e => setFile(e.target.files?.[0] ?? null)} /></label>
      <div className="publish-fields"><label><span className="label-text">页面名称</span><input placeholder="例如：产品介绍页" value={name} onChange={e => setName(e.target.value)} /></label><label><span className="label-text">备注 <span className="optional">可选</span></span><input placeholder="给自己看的描述" value={description} onChange={e => setDescription(e.target.value)} /></label><label><span className="label-text">访问密码 <span className="optional">可选</span></span><input type="password" placeholder="留空则无需密码" value={password} onChange={e => setPassword(e.target.value)} autoComplete="new-password" /></label></div>
      <button className="primary-button publish-submit" disabled={loading}>{loading ? "发布中..." : "立即发布"}<Plus size={17} /></button>
    </form>
    {error && <div className="error-text panel-error">{error}</div>}
  </section>;
}

function StatCard({ icon, label, value, detail }: { icon: ReactNode; label: string; value: string; detail: string }) {
  return <div className="stat-card"><div className="stat-icon">{icon}</div><div><p>{label}</p><strong>{value}</strong><small>{detail}</small></div></div>;
}

function EditModal({ link, onClose, onSaved }: { link: LinkItem; onClose: () => void; onSaved: () => void }) {
  const dialogRef = useDialog(onClose); const [name, setName] = useState(link.name); const [description, setDescription] = useState(link.description); const [password, setPassword] = useState(""); const [clearPassword, setClearPassword] = useState(false); const [file, setFile] = useState<File | null>(null); const [error, setError] = useState(""); const [loading, setLoading] = useState(false);
  async function save(event: FormEvent) { event.preventDefault(); setLoading(true); setError(""); try { await api(`/api/links/${link.id}`, { method: "PATCH", body: formData({ name, description, password, clear_password: clearPassword ? "1" : "" }) }); if (file) await api(`/api/links/${link.id}/upload`, { method: "POST", body: formData({ file }) }); onSaved(); onClose(); } catch (err) { setError(err instanceof Error ? err.message : "保存失败"); } finally { setLoading(false); } }
  return <div className="modal-backdrop" onClick={onClose}><div className="modal" ref={dialogRef} tabIndex={-1} role="dialog" aria-modal="true" aria-label="编辑页面" onClick={e => e.stopPropagation()}><div className="modal-header"><div><p className="eyebrow">EDIT PUBLICATION</p><h2>编辑页面</h2></div><button className="icon-button" onClick={onClose} aria-label="关闭"><X /></button></div><form onSubmit={save} className="modal-form"><label>页面名称<input value={name} onChange={e => setName(e.target.value)} required /></label><label>备注<textarea value={description} onChange={e => setDescription(e.target.value)} rows={3} /></label><label><span className="label-text">访问密码 <small className="field-hint">{clearPassword ? "保存后将移除密码限制" : link.password_protected ? "当前已设置密码，留空则不修改" : "当前无密码，填写后需密码访问"}</small></span><input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="留空则不修改" autoComplete="new-password" disabled={clearPassword} /></label>{link.password_protected && <label className="clear-password"><input type="checkbox" checked={clearPassword} onChange={e => setClearPassword(e.target.checked)} /><span>移除密码保护（保存后任何人都可访问）</span></label>}<label className="replace-file"><span>替换文件 <small>当前为 {link.source_type.toUpperCase()}</small></span><input type="file" accept=".html,.htm,.zip" onChange={e => setFile(e.target.files?.[0] ?? null)} /></label>{file && <div className="selected-file">{file.name}</div>}{error && <div className="error-text">{error}</div>}<div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose}>取消</button><button className="primary-button" disabled={loading}>{loading ? "保存中..." : "保存修改"}<Check size={16} /></button></div></form></div></div>;
}

function StatsModal({ link, onClose }: { link: LinkItem; onClose: () => void }) {
  const dialogRef = useDialog(onClose); const [stats, setStats] = useState<Stats | null>(null); const [error, setError] = useState(""); const [range, setRange] = useState<7 | 30 | 90>(30);
  useEffect(() => { api<Stats>(`/api/links/${link.id}/stats`).then(setStats).catch(err => setError(err.message)); }, [link.id]);
  const daily = [...(stats?.daily ?? [])].reverse().slice(-range);
  const maxPv = Math.max(...(daily.map(item => item.pv) ?? [1]), 1);
  const pv30 = [...(stats?.daily ?? [])].reduce((sum, item) => sum + item.pv, 0);
  const uv30 = stats?.uv ?? 0;
  const last7 = daily.slice(-7).reduce((sum, item) => sum + item.pv, 0);
  const prev7 = daily.slice(-14, -7).reduce((sum, item) => sum + item.pv, 0);
  const trend = prev7 > 0 ? Math.round((last7 - prev7) / prev7 * 100) : (last7 > 0 ? 100 : 0);
  const uvRate = pv30 > 0 ? Math.round(uv30 / pv30 * 100) : 0;
  const avgPv = daily.length ? (pv30 / Math.max(1, (stats?.daily?.length ?? 0))).toFixed(1) : "0";
  const hourly = stats?.hourly ?? [];
  const maxHourly = Math.max(...(hourly.map(item => item.pv) ?? [1]), 1);
  return <div className="modal-backdrop" onClick={onClose}><div className="modal stats-modal" ref={dialogRef} tabIndex={-1} role="dialog" aria-modal="true" aria-label="访问统计" onClick={e => e.stopPropagation()}><div className="modal-header"><div><p className="eyebrow">ANALYTICS / {link.slug}</p><h2>{link.name}</h2></div><button className="icon-button" onClick={onClose} aria-label="关闭"><X /></button></div>{error ? <div className="error-text">{error}</div> : !stats ? <div className="loading-state"><RefreshCw className="spin" /> 正在加载统计...</div> : <div className="stats-content"><div className="mini-stats"><div><span>总浏览量</span><strong>{stats.view_count.toLocaleString()}</strong></div><div><span>独立访客（累计）</span><strong>{stats.total_uv.toLocaleString()}</strong></div><div><span>近 30 天 PV</span><strong>{pv30.toLocaleString()}</strong></div><div><span>近 30 天 UV</span><strong>{uv30.toLocaleString()}</strong></div></div><div className="metrics-row"><div><span>峰值日</span><strong>{stats.peak ? `${stats.peak.day} · ${stats.peak.pv} PV` : "暂无"}</strong></div><div><span>日均 PV</span><strong>{avgPv}</strong></div><div><span>UV / PV 占比</span><strong>{uvRate}%</strong></div><div><span>近 7 天环比</span><strong className={trend >= 0 ? "trend-up" : "trend-down"}>{trend >= 0 ? `↑ ${trend}%` : `↓ ${Math.abs(trend)}%`}</strong></div></div><div className="chart-block"><div className="block-title"><span>每日访问</span><div className="range-tabs"><button className={range === 7 ? "active" : ""} onClick={() => setRange(7)}>7 天</button><button className={range === 30 ? "active" : ""} onClick={() => setRange(30)}>30 天</button><button className={range === 90 ? "active" : ""} onClick={() => setRange(90)}>90 天</button></div></div><div className="chart-legend"><span><i className="legend-pv" />PV</span><span><i className="legend-uv" />UV</span></div><div className="bar-chart">{daily.map(item => <div className="bar-column" key={item.day} title={`${item.day}：${item.pv} PV / ${item.uv} UV`}><div className="bar-pair"><div className="bar pv" style={{ height: `${Math.max(4, item.pv / maxPv * 100)}%` }} /><div className="bar uv" style={{ height: `${Math.max(4, item.uv / maxPv * 100)}%` }} /></div><small>{item.day.slice(5)}</small></div>)}</div></div><div className="chart-block"><div className="block-title"><span>最近 24 小时</span><small>按小时</small></div><div className="chart-legend"><span><i className="legend-pv" />PV</span><span><i className="legend-uv" />UV</span></div>{hourly.length ? <div className="bar-chart hourly-chart">{hourly.map(item => <div className="bar-column" key={item.hour} title={`${item.hour}：${item.pv} PV / ${item.uv} UV`}><div className="bar-pair"><div className="bar pv" style={{ height: `${Math.max(4, item.pv / maxHourly * 100)}%` }} /><div className="bar uv" style={{ height: `${Math.max(4, item.uv / maxHourly * 100)}%` }} /></div><small>{item.hour.slice(11)}时</small></div>)}</div> : <div className="empty-small">最近 24 小时暂无访问</div>}</div><div className="breakdown-grid"><div className="breakdown"><div className="block-title"><span>浏览器</span></div>{stats.browsers.length ? stats.browsers.map(item => <div className="break-row" key={item.name}><span>{item.name}</span><strong>{item.value}</strong></div>) : <div className="empty-small">暂无数据</div>}</div><div className="breakdown"><div className="block-title"><span>设备</span></div>{stats.devices.length ? stats.devices.map(item => <div className="break-row" key={item.name}><span>{item.name}</span><strong>{item.value}</strong></div>) : <div className="empty-small">暂无数据</div>}</div><div className="breakdown"><div className="block-title"><span>操作系统</span></div>{stats.os.length ? stats.os.map(item => <div className="break-row" key={item.name}><span>{item.name}</span><strong>{item.value}</strong></div>) : <div className="empty-small">暂无数据</div>}</div><div className="breakdown"><div className="block-title"><span>访问来源</span></div>{stats.referers.length ? stats.referers.map(item => <div className="break-row" key={item.name} title={item.name}><span className="ref-name">{item.name}</span><strong>{item.value}</strong></div>) : <div className="empty-small">暂无数据</div>}</div></div><div className="recent-block"><div className="block-title"><span>最近访问</span><small>最近 20 条</small></div>{stats.recent.length ? <ul className="recent-list">{stats.recent.map((item, index) => <li key={index}><span className="recent-time">{formatDate(item.visited_at)}</span><span className="recent-agent">{item.browser} · {item.os} · {item.device === "mobile" ? "移动端" : "桌面端"}</span><span className="recent-ref" title={item.referer}>{item.referer || "直接访问"}</span></li>)}</ul> : <div className="empty-small">暂无访问记录</div>}</div></div>}</div></div>;
}

function PublishedModal({ link, onClose }: { link: LinkItem; onClose: () => void }) {
  const dialogRef = useDialog(onClose);
  const [copied, setCopied] = useState(false);
  const qrRef = useRef<HTMLCanvasElement | null>(null);
  useEffect(() => { if (qrRef.current) drawQrWithLogo(qrRef.current, link.url); }, [link.url]);
  async function copy() {
    try { await navigator.clipboard.writeText(link.url); } catch {
      const el = document.createElement("textarea"); el.value = link.url; el.style.position = "fixed"; el.style.opacity = "0"; document.body.appendChild(el); el.select(); try { document.execCommand("copy"); } catch { /* ignore */ } el.remove();
    }
    setCopied(true); window.setTimeout(() => setCopied(false), 1600);
  }
  function downloadQr() {
    const canvas = qrRef.current; if (!canvas) return;
    const a = document.createElement("a");
    a.href = canvas.toDataURL("image/png");
    a.download = `${link.slug}-qrcode.png`;
    a.click();
  }
  return <div className="modal-backdrop" onClick={onClose}><div className="modal published-modal" ref={dialogRef} tabIndex={-1} role="dialog" aria-modal="true" aria-label="发布成功" onClick={e => e.stopPropagation()}><div className="published-icon"><Check size={22} /></div><h2>页面已发布</h2><p className="muted">链接已就绪，复制或打开即可访问{link.password_protected ? "（已开启密码保护）" : ""}：</p><div className="published-url">{link.url}</div><div className="published-qr"><canvas ref={qrRef} role="img" aria-label="页面链接二维码" /><button className="secondary-button qr-download" onClick={downloadQr}>下载二维码<FileArchive size={15} /></button></div><div className="modal-actions"><button className="secondary-button" onClick={onClose}>完成</button><a className="primary-button" href={link.url} target="_blank" rel="noreferrer">打开页面<ExternalLink size={16} /></a><button className="primary-button" onClick={copy}>{copied ? "已复制" : "复制链接"}<Clipboard size={16} /></button></div></div></div>;
}

function ChangePasswordModal({ onClose, onChanged }: { onClose: () => void; onChanged: () => void }) {
  const dialogRef = useDialog(onClose); const [oldPassword, setOldPassword] = useState(""); const [newPassword, setNewPassword] = useState(""); const [confirm, setConfirm] = useState(""); const [error, setError] = useState(""); const [loading, setLoading] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (newPassword.length < 6) { setError("新密码至少 6 位"); return; }
    if (newPassword !== confirm) { setError("两次输入的新密码不一致"); return; }
    setLoading(true); setError("");
    try { await api("/api/auth/password", { method: "POST", body: formData({ old_password: oldPassword, new_password: newPassword }) }); onChanged(); onClose(); }
    catch (err) { setError(err instanceof Error ? err.message : "修改失败"); }
    finally { setLoading(false); }
  }
  return <div className="modal-backdrop" onClick={onClose}><div className="modal" ref={dialogRef} tabIndex={-1} role="dialog" aria-modal="true" aria-label="修改密码" onClick={e => e.stopPropagation()}><div className="modal-header"><div><p className="eyebrow">ACCOUNT SECURITY</p><h2>修改密码</h2></div><button className="icon-button" onClick={onClose} aria-label="关闭"><X /></button></div><form onSubmit={submit} className="modal-form"><label><span className="label-text">当前密码</span><input type="password" value={oldPassword} onChange={e => setOldPassword(e.target.value)} autoComplete="current-password" required /></label><label><span className="label-text">新密码 <span className="optional">至少 6 位</span></span><input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} autoComplete="new-password" required /></label><label><span className="label-text">确认新密码</span><input type="password" value={confirm} onChange={e => setConfirm(e.target.value)} autoComplete="new-password" required /></label>{error && <div className="error-text">{error}</div>}<div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose}>取消</button><button className="primary-button" disabled={loading}>{loading ? "保存中..." : "确认修改"}<Check size={16} /></button></div></form></div></div>;
}

function QrModal({ link, onClose }: { link: LinkItem; onClose: () => void }) {
  const dialogRef = useDialog(onClose);
  const [copied, setCopied] = useState(false);
  const qrRef = useRef<HTMLCanvasElement | null>(null);
  useEffect(() => { if (qrRef.current) drawQrWithLogo(qrRef.current, link.url); }, [link.url]);
  async function copy() {
    try { await navigator.clipboard.writeText(link.url); } catch {
      const el = document.createElement("textarea"); el.value = link.url; el.style.position = "fixed"; el.style.opacity = "0"; document.body.appendChild(el); el.select(); try { document.execCommand("copy"); } catch { /* ignore */ } el.remove();
    }
    setCopied(true); window.setTimeout(() => setCopied(false), 1600);
  }
  function downloadQr() {
    const canvas = qrRef.current; if (!canvas) return;
    const a = document.createElement("a");
    a.href = canvas.toDataURL("image/png");
    a.download = `${link.slug}-qrcode.png`;
    a.click();
  }
  return <div className="modal-backdrop" onClick={onClose}><div className="modal qr-modal" ref={dialogRef} tabIndex={-1} role="dialog" aria-modal="true" aria-label="页面二维码" onClick={e => e.stopPropagation()}><div className="modal-header"><div><p className="eyebrow">QR CODE / {link.slug}</p><h2>{link.name}</h2></div><button className="icon-button" onClick={onClose} aria-label="关闭"><X /></button></div><div className="qr-body"><canvas ref={qrRef} role="img" aria-label="页面链接二维码" /><div className="qr-url">{link.url}</div><div className="modal-actions"><button className="secondary-button" onClick={downloadQr}>下载二维码<FileArchive size={15} /></button><button className="primary-button" onClick={copy}>{copied ? "已复制" : "复制链接"}<Clipboard size={16} /></button></div></div></div></div>;
}

function Dashboard({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [links, setLinks] = useState<LinkItem[]>([]); const [query, setQuery] = useState(""); const [page, setPage] = useState(1); const [total, setTotal] = useState(0); const [summary, setSummary] = useState({ total: 0, total_views: 0, active: 0 }); const [activeNav, setActiveNav] = useState<"overview" | "pages">("overview"); const [editing, setEditing] = useState<LinkItem | null>(null); const [viewing, setViewing] = useState<LinkItem | null>(null); const [published, setPublished] = useState<LinkItem | null>(null); const [qrLink, setQrLink] = useState<LinkItem | null>(null); const [passwordOpen, setPasswordOpen] = useState(false); const [userInfo, setUserInfo] = useState(user); const [menuAnchor, setMenuAnchor] = useState<{ id: number; x: number; y: number } | null>(null); const [copiedId, setCopiedId] = useState<number | null>(null); const [health, setHealth] = useState<"checking" | "ok" | "down">("checking"); const [bannerDismissed, setBannerDismissed] = useState(false); const [toast, setToast] = useState(""); const [error, setError] = useState("");
  const PAGE_SIZE = 8;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const refresh = (targetPage: number = page) => api<LinkListResponse>(`/api/links?page=${targetPage}&page_size=${PAGE_SIZE}`).then(data => { setLinks(data.items); setTotal(data.total); setPage(data.page); }).catch(err => setError(err.message));
  const refreshSummary = () => api<typeof summary>("/api/links/summary").then(setSummary).catch(() => { });
  useEffect(() => { refresh(1); refreshSummary(); }, []);
  useEffect(() => {
    let alive = true;
    const check = async () => {
      try { const res = await fetch("/api/health", { credentials: "include" }); if (alive) setHealth(res.ok ? "ok" : "down"); } catch { if (alive) setHealth("down"); }
    };
    check();
    const timer = window.setInterval(check, 15000);
    return () => { alive = false; window.clearInterval(timer); };
  }, []);
  useEffect(() => {
    if (!menuAnchor) return;
    const close = () => setMenuAnchor(null);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => { window.removeEventListener("scroll", close, true); window.removeEventListener("resize", close); };
  }, [menuAnchor]);
  const filtered = useMemo(() => links.filter(link => `${link.name} ${link.slug} ${link.description}`.toLowerCase().includes(query.toLowerCase())), [links, query]);
  async function action(link: LinkItem, type: "enable" | "disable" | "delete") { if (type === "delete" && !window.confirm(`确定删除“${link.name}”吗？`)) return; try { await api(`/api/links/${link.id}${type === "delete" ? "" : `/${type}`}`, { method: type === "delete" ? "DELETE" : "POST" }); refresh(); refreshSummary(); showToast(type === "delete" ? "页面已删除" : type === "disable" ? "已停止访问" : "已恢复访问"); } catch (err) { setError(err instanceof Error ? err.message : "操作失败"); } }
  function showToast(message: string) { setToast(message); window.setTimeout(() => setToast(""), 2400); }
  async function copy(value: string, id?: number) {
    try { await navigator.clipboard.writeText(value); } catch {
      const el = document.createElement("textarea"); el.value = value; el.style.position = "fixed"; el.style.opacity = "0"; document.body.appendChild(el); el.select(); try { document.execCommand("copy"); } catch { /* ignore */ } el.remove();
    }
    if (id !== undefined) { setCopiedId(id); window.setTimeout(() => setCopiedId(null), 1600); }
    showToast("链接已复制");
  }
  const publish = () => { setActiveNav("overview"); setTimeout(() => document.querySelector(".publish-panel")?.scrollIntoView({ behavior: "smooth", block: "start" }), 60); };
  /** 分页页码序列：首尾 + 当前页前后，中间用省略号折叠 */
  function pageItems(current: number, total: number): (number | "…")[] {
    if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
    const wanted = [...new Set([1, total, current - 1, current, current + 1])].filter(p => p >= 1 && p <= total).sort((a, b) => a - b);
    const result: (number | "…")[] = [];
    let prev = 0;
    for (const p of wanted) {
      if (p - prev > 1) result.push("…");
      result.push(p);
      prev = p;
    }
    return result;
  }
  return <div className="app-shell"><aside className="sidebar"><div className="brand-mark"><BrandLogo /> HTML Drop</div><nav><button className={`nav-item ${activeNav === "overview" ? "active" : ""}`} onClick={() => { setActiveNav("overview"); window.scrollTo({ top: 0, behavior: "smooth" }); }}><LayoutDashboard size={17} />概览</button><button className={`nav-item ${activeNav === "pages" ? "active" : ""}`} onClick={() => setActiveNav("pages")}><Archive size={17} />全部页面 <b>{summary.total}</b></button></nav><div className="sidebar-bottom"><div className="account"><div className="avatar">{userInfo.username.slice(0, 1).toUpperCase()}</div><div><strong>{userInfo.username}</strong><small>个人空间</small></div></div><button className="logout-button" onClick={() => setPasswordOpen(true)}><KeyRound size={16} />修改密码</button><button className="logout-button" onClick={onLogout}><LogOut size={16} />退出登录</button></div></aside><main className="main-content"><header className="topbar"><div><p className="eyebrow">{activeNav === "pages" ? "PUBLICATIONS" : "OVERVIEW"}</p><h1>{activeNav === "pages" ? "我的页面" : "页面发布"}</h1></div><div className="topbar-meta"><span className={`status-dot ${health}`} />{health === "ok" ? "服务运行正常" : health === "down" ? "服务连接断开" : "检查服务中"}<button className="icon-button" onClick={() => { setError(""); refresh(); }} aria-label="刷新"><RefreshCw size={17} /></button></div></header><div className="content-wrap">{userInfo.default_password && !bannerDismissed && <div className="alert banner-warn"><span>当前仍在使用默认密码（admin123），请通过环境变量 <code>ADMIN_PASSWORD</code> 修改后重启服务，或点击左下角「修改密码」。</span><button onClick={() => setBannerDismissed(true)} aria-label="关闭提示"><X size={15} /></button></div>}{error && <div className="alert error-text">{error}<button onClick={() => setError("")}><X size={15} /></button></div>}{activeNav === "overview" && <><div className="stats-grid"><StatCard icon={<FileCode2 />} label="页面总数" value={String(summary.total)} detail={`${summary.active} 个正在访问`} /><StatCard icon={<Activity />} label="累计浏览" value={summary.total_views.toLocaleString()} detail="所有页面合计" /><StatCard icon={<BarChart3 />} label="平均浏览" value={summary.total ? (summary.total_views / summary.total).toFixed(1) : "0"} detail="每个页面平均" /></div><UploadPanel onCreated={link => { setActiveNav("pages"); refresh(1); refreshSummary(); setPublished(link); }} /></>}{activeNav === "pages" && <section className="links-section"><div className="section-heading list-heading"><div><p className="eyebrow">YOUR PUBLICATIONS</p><h2>我的页面 <span>{total}</span></h2></div><label className="search-box"><Search size={17} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="搜索页面" /></label></div><div className="table-wrap"><table><thead><tr><th scope="col">页面</th><th scope="col">访问地址</th><th scope="col">状态</th><th scope="col">浏览量</th><th scope="col">更新时间</th><th scope="col" aria-label="操作" /></tr></thead><tbody>{filtered.map(link => <tr key={link.id}><td><div className="page-name"><div className={`file-icon ${link.source_type}`}><FileCode2 size={17} /></div><div><strong>{link.name}{link.password_protected && <Lock size={11} className="lock-icon" aria-label="密码保护" />}</strong><small>{link.description || `${link.source_type.toUpperCase()} 静态页面`}</small></div></div></td><td><button className="link-url" onClick={() => copy(link.url)} title="复制链接">{link.url.replace(/^https?:\/\//, "")}<Clipboard size={14} /></button></td><td><span className={`status ${link.status}`}><i />{link.status === "active" ? "访问中" : "已停止"}</span></td><td><strong className="views">{link.view_count.toLocaleString()}</strong></td><td className="date-cell">{formatDate(link.updated_at)}</td><td><div className="row-actions"><a className="icon-button" href={link.url} target="_blank" rel="noreferrer" aria-label="打开页面"><ExternalLink size={16} /></a><button className="icon-button" onClick={() => setQrLink(link)} aria-label="查看二维码"><QrCode size={16} /></button><button className={`icon-button ${copiedId === link.id ? "copied" : ""}`} onClick={() => copy(link.url, link.id)} aria-label={copiedId === link.id ? "已复制" : "复制链接"}>{copiedId === link.id ? <Check size={16} /> : <Clipboard size={16} />}</button><div className="menu-wrap"><button className="icon-button" onClick={e => { const rect = e.currentTarget.getBoundingClientRect(); setMenuAnchor(menuAnchor?.id === link.id ? null : { id: link.id, x: rect.right, y: rect.bottom }); }} aria-haspopup="menu" aria-expanded={menuAnchor?.id === link.id} aria-label="更多操作"><MoreHorizontal size={16} /></button>{menuAnchor?.id === link.id && <><div className="menu-backdrop" onClick={() => setMenuAnchor(null)} /><div className="row-menu" role="menu" style={{ top: menuAnchor.y + 6, right: window.innerWidth - menuAnchor.x, maxHeight: `calc(100vh - ${menuAnchor.y + 12}px)`, overflowY: "auto" }}><button role="menuitem" onClick={() => { setMenuAnchor(null); setViewing(link); }}><BarChart3 size={14} />查看统计</button><button role="menuitem" onClick={() => { setMenuAnchor(null); setEditing(link); }}><Pencil size={14} />编辑</button><button role="menuitem" onClick={() => { setMenuAnchor(null); action(link, link.status === "active" ? "disable" : "enable"); }}>{link.status === "active" ? <Pause size={14} /> : <Play size={14} />}{link.status === "active" ? "停止访问" : "恢复访问"}</button><button role="menuitem" className="menu-danger" onClick={() => { setMenuAnchor(null); action(link, "delete"); }}><Trash2 size={14} />删除</button></div></>}</div></div></td></tr>)}</tbody></table>{!filtered.length && <div className="empty-state"><FileUp size={28} /><strong>{query ? "没有匹配的页面" : "还没有发布页面"}</strong><span>{query ? "换个关键词试试" : "发布一个页面后会显示在这里"}</span>{!query && <button className="primary-button" onClick={publish}><Plus size={15} />去发布</button>}</div>}{totalPages > 1 && <div className="pagination"><button className="secondary-button" disabled={page <= 1} onClick={() => refresh(page - 1)}>上一页</button>{pageItems(page, totalPages).map((item, index) => item === "…" ? <span key={`e${index}`} className="page-ellipsis">…</span> : <button key={item} className={`page-btn ${item === page ? "active" : ""}`} onClick={() => refresh(item)}>{item}</button>)}<button className="secondary-button" disabled={page >= totalPages} onClick={() => refresh(page + 1)}>下一页</button><span className="page-total">共 {total} 条</span></div>}</div></section>}</div></main>{editing && <EditModal link={editing} onClose={() => setEditing(null)} onSaved={() => { refresh(); showToast("修改已保存"); }} />}{viewing && <StatsModal link={viewing} onClose={() => setViewing(null)} />}{published && <PublishedModal link={published} onClose={() => setPublished(null)} />}{qrLink && <QrModal link={qrLink} onClose={() => setQrLink(null)} />}{passwordOpen && <ChangePasswordModal onClose={() => setPasswordOpen(false)} onChanged={() => { setUserInfo(current => ({ ...current, default_password: false })); showToast("密码已修改"); }} />}{toast && <div className="toast" role="status" aria-live="polite"><Check size={17} />{toast}</div>}</div>;
}

export default function App() {
  const [user, setUser] = useState<User | null>(null); const [checking, setChecking] = useState(true);
  useEffect(() => { api<User>("/api/auth/me").then(setUser).catch(() => { setApiToken(null); setUser(null); }).finally(() => setChecking(false)); }, []);
  if (checking) return <div className="loading-screen"><RefreshCw className="spin" /></div>;
  if (!user) return <Login onLogin={setUser} />;
  return <Dashboard user={user} onLogout={async () => { try { await api("/api/auth/logout", { method: "POST" }); } finally { setApiToken(null); setUser(null); } }} />;
}

/**
 * Hestia UI kit — code counterparts of the Figma components
 * (Button, Badge, Icon Button, Card Header, Stat) plus small shared pieces.
 */
import type { LucideIcon } from "lucide-react";
import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

import { ApiError } from "@/lib/api";

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

/* ---------------- Badge ---------------- */
export type Tone = "accent" | "success" | "data" | "warning" | "neutral" | "danger";
const TONE_DOT: Record<Tone, string> = {
  accent: "bg-ember", success: "bg-ok", data: "bg-data", warning: "bg-warn", neutral: "bg-fg-3", danger: "bg-danger",
};
const TONE_TEXT: Record<Tone, string> = {
  accent: "text-ember", success: "text-ok", data: "text-data", warning: "text-warn", neutral: "text-fg-2", danger: "text-danger",
};
export function Badge({ tone = "neutral", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span className={cx("glass inline-flex items-center gap-2 rounded-full px-3 py-2 whitespace-nowrap", className)}>
      <span aria-hidden className={cx("size-1.5 rounded-full", TONE_DOT[tone])} />
      <span className={cx("t-caps-s", TONE_TEXT[tone])}>{children}</span>
    </span>
  );
}

/* ---------------- Button ---------------- */
type ButtonStyle = "primary" | "accent" | "secondary";
const BUTTON: Record<ButtonStyle, string> = {
  primary: "bg-inverse text-fg-inverse hover:bg-white/90",
  accent: "bg-ember text-fg-inverse glow-ember hover:brightness-110",
  secondary: "border border-line-strong text-fg hover:bg-raised",
};
type ButtonProps = {
  variant?: ButtonStyle;
  icon?: boolean;
  href?: string;
  className?: string;
  children: ReactNode;
} & Omit<ComponentProps<"button">, "className" | "children">;
export function Button({ variant = "primary", icon = true, href, className, children, ...rest }: ButtonProps) {
  const cls = cx(
    "t-caps inline-flex items-center justify-center gap-3 rounded-full px-6 py-3 transition disabled:opacity-50 disabled:pointer-events-none",
    BUTTON[variant],
    className,
  );
  const inner = (
    <>
      {children}
      {icon && <ArrowUpRight aria-hidden size={16} strokeWidth={1.75} />}
    </>
  );
  return href ? (
    <Link href={href} className={cls}>{inner}</Link>
  ) : (
    <button type="button" className={cls} {...rest}>{inner}</button>
  );
}

/* ---------------- Icon Button ---------------- */
export function IconButton({
  icon: Icon, label, href, size = 44, className, ...rest
}: { icon: LucideIcon; label: string; href?: string; size?: 36 | 40 | 44; className?: string } & Omit<ComponentProps<"button">, "className">) {
  const cls = cx("glass inline-flex shrink-0 items-center justify-center rounded-full text-fg transition hover:border-line-strong", className);
  const style = { width: size, height: size };
  const icon = <Icon aria-hidden size={18} strokeWidth={1.75} />;
  return href ? (
    <Link href={href} aria-label={label} className={cls} style={style}>{icon}</Link>
  ) : (
    <button type="button" aria-label={label} className={cls} style={style} {...rest}>{icon}</button>
  );
}

/* ---------------- Card + Card Header ---------------- */
export function Card({ className, children, accent }: { className?: string; children: ReactNode; accent?: boolean }) {
  return (
    <section className={cx("glass flex flex-col gap-3.5 rounded-lg p-5", accent && "border-ember-line!", className)}>
      {children}
    </section>
  );
}
export function CardHeader({ title, meta }: { title: string; meta?: string }) {
  return (
    <header className="flex items-center justify-between gap-3 whitespace-nowrap">
      <h2 className="t-caps text-fg">{title}</h2>
      {meta && <span className="t-mono-s text-fg-3">{meta}</span>}
    </header>
  );
}

/* ---------------- Stat (stats rail) ---------------- */
export function Stat({ icon: Icon, value, label }: { icon: LucideIcon; value: ReactNode; label: string }) {
  return (
    <div className="flex w-[120px] flex-col items-center gap-1.5 text-center">
      <Icon aria-hidden size={18} strokeWidth={1.75} className="text-ember" />
      <span className="t-data-l text-fg">{value}</span>
      <span className="t-caps-s text-fg-3">{label}</span>
    </div>
  );
}

/* ---------------- Citation chip ---------------- */
export function Citation({ ntrsId, page, url }: { ntrsId: string; page?: number | null; url?: string | null }) {
  const body = <span className="t-mono-s text-ember-soft normal-case">[{ntrsId}{page != null ? `, p.${page}` : ""}]</span>;
  const cls = "inline-flex rounded-sm border border-ember-line bg-ember-tint px-2 py-0.5";
  return url ? (
    <a href={url} target="_blank" rel="noreferrer" className={cx(cls, "hover:border-ember")}>{body}</a>
  ) : (
    <span className={cls}>{body}</span>
  );
}

/* ---------------- Progress / relevance bar ---------------- */
export function Bar({ value, color = "bg-ember", height = 4, className }: { value: number; color?: string; height?: number; className?: string }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className={cx("w-full overflow-hidden rounded-full bg-raised", className)} style={{ height }}>
      <div className={cx("h-full rounded-full", color)} style={{ width: `${pct}%` }} />
    </div>
  );
}

/* ---------------- Segmented control ---------------- */
export function Segmented<T extends string>({
  options, value, onChange, label, className, size = "md",
}: {
  options: { value: T; label: string }[]; value: T; onChange: (v: T) => void; label: string;
  className?: string; size?: "sm" | "md";
}) {
  return (
    <div role="radiogroup" aria-label={label} className={cx("inline-flex gap-0.5 rounded-full border border-line bg-raised p-[3px]", className)}>
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={on}
            onClick={() => onChange(o.value)}
            className={cx(
              "flex-1 rounded-full whitespace-nowrap transition",
              size === "sm" ? "px-2.5 py-1 text-[12px]" : "px-3 py-1.5 text-[13px]",
              on ? "bg-ember font-medium text-fg-inverse" : "text-fg-2 hover:text-fg",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

/* ---------------- Key/value row ---------------- */
export function Fact({ label, value, top = true }: { label: string; value: ReactNode; top?: boolean }) {
  return (
    <div className={cx("flex items-center justify-between gap-4 py-2.5", top ? "border-t border-line" : "border-b border-line")}>
      <span className="t-caps-s text-fg-3">{label}</span>
      <span className="t-mono-m text-right text-fg">{value}</span>
    </div>
  );
}

/* ---------------- Page header ---------------- */
export function PageHeader({ badge, title, subtitle, aside }: { badge?: ReactNode; title: ReactNode; subtitle?: string; aside?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-6">
      <div className="flex flex-col gap-3">
        {badge}
        <h1 className="t-display-l text-fg">{title}</h1>
        {subtitle && <p className="t-body-m text-fg-2">{subtitle}</p>}
      </div>
      {aside}
    </div>
  );
}

/* ---------------- States ---------------- */
export function Loading({ label = "Loading…" }: { label?: string }) {
  return <p className="t-body-s animate-pulse text-fg-3">{label}</p>;
}
export function ErrorBox({ error }: { error: unknown }) {
  const message = error instanceof ApiError || error instanceof Error ? error.message : String(error);
  return (
    <div role="alert" className="t-body-s rounded-md border border-danger/40 bg-danger/10 p-4 text-danger">
      {message}
    </div>
  );
}

export { cx };

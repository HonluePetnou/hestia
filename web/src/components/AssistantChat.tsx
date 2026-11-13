"use client";

import { ArrowUpRight, FileText, Flame, Send, Sparkles } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { Badge, Card, CardHeader, ErrorBox, cx } from "@/components/ui";
import { api, type Schemas } from "@/lib/api";
import { ASSISTANT_SUGGESTIONS } from "@/lib/content";

type Msg =
  | { role: "user"; text: string }
  | { role: "ai"; res: Schemas["AskResponse"]; ms: number }
  | { role: "error"; error: unknown };

const CITE_SPLIT = /(\[[^\]]+?, p\.\s?\d+\])/;
const CITE = /^\[([^\],]+?), p\.\s?(\d+)\]$/;

function Answer({ text, citations }: { text: string; citations: Schemas["Citation"][] }) {
  const urls = new Map(citations.map((c) => [`${c.ntrs_id}:${c.page}`, c.url]));
  return (
    <p className="t-body-m text-fg">
      {text.split(CITE_SPLIT).map((part, i) => {
        const m = CITE.exec(part);
        if (!m) return <span key={i}>{part}</span>;
        const url = urls.get(`${m[1].trim()}:${m[2]}`);
        const cls = "font-mono text-[13px] font-medium text-ember";
        return url ? (
          <a key={i} href={url} target="_blank" rel="noreferrer" className={cx(cls, "underline-offset-2 hover:underline")}>{part}</a>
        ) : (
          <span key={i} className={cls}>{part}</span>
        );
      })}
    </p>
  );
}

const PROVIDER_LABEL: Record<string, string> = { gemini: "Gemini", openai: "OpenAI", anthropic: "Claude", mock: "Mock (no LLM)" };

/** Previous turns sent with each question so follow-ups ("and on Mars?") keep context. */
function toHistory(messages: Msg[]): Schemas["ChatMessage"][] {
  return messages
    .flatMap((m): Schemas["ChatMessage"][] =>
      m.role === "user" ? [{ role: "user", content: m.text }] : m.role === "ai" ? [{ role: "assistant", content: m.res.answer }] : [],
    )
    .slice(-6);
}

export function AssistantChat() {
  const params = useSearchParams();
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [stats, setStats] = useState<Schemas["StatsResponse"]>();
  const asked = useRef(false);
  const end = useRef<HTMLDivElement>(null);

  async function ask(question: string) {
    const q = question.trim();
    if (q.length < 3 || pending) return;
    setInput("");
    setPending(true);
    const history = toHistory(messages);
    setMessages((m) => [...m, { role: "user", text: q }]);
    const t0 = performance.now();
    try {
      const res = await api.ask(q, history);
      setMessages((m) => [...m, { role: "ai", res, ms: performance.now() - t0 }]);
    } catch (error) {
      setMessages((m) => [...m, { role: "error", error }]);
    } finally {
      setPending(false);
    }
  }

  useEffect(() => {
    api.stats().then(setStats, () => undefined);
  }, []);
  useEffect(() => {
    const q = params.get("q");
    if (q && !asked.current) { asked.current = true; void ask(q); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);
  // Braces matter: scrollIntoView() can return a Promise, and an effect may only return a cleanup function.
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, pending]);

  const lastAi = [...messages].reverse().find((m): m is Extract<Msg, { role: "ai" }> => m.role === "ai");
  const sources = lastAi?.res.citations ?? [];
  const onSubmit = (e: FormEvent) => { e.preventDefault(); void ask(input); };

  return (
    <div className="grid flex-1 gap-4 xl:grid-cols-[1fr_420px]">
      <div className="flex min-h-[640px] flex-col gap-5">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-col gap-2.5">
            <Badge tone="success" className="self-start">Grounded in {stats?.documents ?? "…"} NASA reports</Badge>
            <h1 className="t-display-l">Ask Hestia</h1>
          </div>
          <Badge tone={stats?.llm_provider === "mock" ? "warning" : undefined}>Model · {stats ? (PROVIDER_LABEL[stats.llm_provider] ?? stats.llm_provider) : "…"}</Badge>
        </div>

        <div className="flex flex-1 flex-col gap-[18px]" aria-live="polite">
          {messages.length === 0 && (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
              <Sparkles aria-hidden size={28} strokeWidth={1.5} className="text-ember" />
              <p className="t-h2">What do you want to know about fire in space?</p>
              <p className="t-body-s max-w-md text-fg-3">Answers come only from indexed NASA reports and always cite their source. If the sources don’t cover it, Hestia says so.</p>
            </div>
          )}
          {messages.map((m, i) =>
            m.role === "user" ? (
              <div key={i} className="flex justify-end">
                <p className="t-body-m rounded-lg rounded-br-md border border-line-strong bg-raised px-[18px] py-3">{m.text}</p>
              </div>
            ) : (
              <div key={i} className="flex gap-3.5">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-full border border-ember-line bg-ember-tint">
                  <Flame aria-hidden size={18} strokeWidth={1.75} className="text-ember" />
                </span>
                <div className={cx("glass flex flex-1 flex-col gap-3 rounded-lg rounded-tl-md px-5 py-4", m.role === "ai" && m.res.insufficient_data && "border-line-strong!")}>
                  {m.role === "error" ? (
                    <ErrorBox error={m.error} />
                  ) : (
                    <>
                      <div className="flex items-center gap-2.5">
                        <span className="t-h3 text-[17px]">Hestia</span>
                        <span className="t-mono-s text-fg-3">{m.res.citations.length} sources · {(m.ms / 1000).toFixed(1)} s</span>
                      </div>
                      {m.res.insufficient_data && <Badge tone="warning" className="self-start">Insufficient data</Badge>}
                      <Answer text={m.res.answer} citations={m.res.citations} />
                    </>
                  )}
                </div>
              </div>
            ),
          )}
          {pending && <p className="t-body-s animate-pulse pl-12 text-fg-3">Searching NASA reports…</p>}
          <div ref={end} />
        </div>

        <div className="flex flex-wrap gap-2">
          {ASSISTANT_SUGGESTIONS.map((s) => (
            <button key={s} type="button" onClick={() => void ask(s)} disabled={pending} className="glass t-body-s flex items-center gap-2 rounded-full px-3.5 py-2 text-fg-2 hover:text-fg disabled:opacity-50">
              <Sparkles aria-hidden size={13} className="text-ember" /> {s}
            </button>
          ))}
        </div>
        <form onSubmit={onSubmit} className="glass glow-ember flex items-center gap-3 rounded-full border-ember-line! py-2 pr-2 pl-[22px]">
          <label htmlFor="ask-input" className="sr-only">Question</label>
          <input
            id="ask-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about NASA microgravity fire data…"
            className="t-body-m min-w-0 flex-1 bg-transparent text-fg outline-none placeholder:text-fg-3"
          />
          <span className="t-caps-s hidden text-fg-3 md:inline">Answers always cite sources</span>
          <button type="submit" aria-label="Send question" disabled={pending || input.trim().length < 3} className="flex size-11 items-center justify-center rounded-full bg-ember text-fg-inverse transition disabled:opacity-40">
            <Send aria-hidden size={18} strokeWidth={1.75} />
          </button>
        </form>
      </div>

      <Card className="gap-3.5 p-5">
        <CardHeader title="Sources" meta={`${sources.length} cited`} />
        {sources.length === 0 && <p className="t-body-s text-fg-3">Sources cited in the latest answer appear here.</p>}
        {sources.map((s, i) => (
          <article key={`${s.ntrs_id}-${s.page}`} className={cx("flex flex-col gap-2.5 rounded-md border bg-raised px-4 py-3.5", i === 0 ? "border-ember-line" : "border-line")}>
            <div className="flex items-center gap-2">
              <span className="t-mono-s flex size-[22px] items-center justify-center rounded-full bg-ember-tint text-ember">{i + 1}</span>
              <span className="t-mono-s flex-1 text-fg-2">NTRS {s.ntrs_id}</span>
              <span className="t-mono-s normal-case text-fg-3">p.{s.page}</span>
            </div>
            <p className="text-[15px] font-medium leading-snug">{s.title}</p>
            <a href={s.url} target="_blank" rel="noreferrer" className="t-caps-s flex items-center gap-1.5 text-ember hover:text-ember-soft">
              Open PDF at p.{s.page} <ArrowUpRight aria-hidden size={12} />
            </a>
          </article>
        ))}
        <div className="mt-auto flex gap-2.5 rounded-md border border-ember-line bg-ember-tint px-3.5 py-3">
          <FileText aria-hidden size={16} className="mt-0.5 shrink-0 text-ember" />
          <p className="t-body-s text-ember-soft">Every claim links to a NASA page. If the sources don’t contain the answer, Hestia says so.</p>
        </div>
      </Card>
    </div>
  );
}

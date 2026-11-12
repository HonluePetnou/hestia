"use client";

import { type FormEvent, useState } from "react";

import { ErrorBox, Json, PageHeader } from "@/components/ui";
import { api, type Schemas } from "@/lib/api";

export default function Page() {
  const [question, setQuestion] = useState("How does flame spread differ in microgravity?");
  const [answer, setAnswer] = useState<Schemas["AskResponse"] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      setAnswer(await api.ask(question));
    } catch (err) {
      setError(err);
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <PageHeader title="AI Assistant" subtitle="Answers grounded in NASA sources, with citations." />
      <form onSubmit={onSubmit} className="mb-6 flex max-w-2xl gap-2">
        <label htmlFor="question" className="sr-only">
          Question
        </label>
        <input
          id="question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          className="flex-1 rounded border border-gray-300 px-3 py-2"
        />
        <button
          type="submit"
          disabled={pending || question.trim().length < 3}
          className="rounded border border-gray-300 px-4 py-2 disabled:opacity-50"
        >
          {pending ? "Asking…" : "Ask"}
        </button>
      </form>
      {error !== null && <ErrorBox error={error} />}
      {answer && <Json data={answer} />}
    </>
  );
}

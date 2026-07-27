// Serverless function: POST /api/ask
// Runs on Vercel's server (NOT the browser), so it can safely use the secret key.
// It embeds the question, finds the closest chunks in Supabase, and asks OpenAI.

import OpenAI from "openai";
import { createClient } from "@supabase/supabase-js";
import { retrieveEvidence } from "../lib/retrieval/retrieve-evidence.js";

const SYSTEM_PROMPT =
  "You are the Greater Change Health company brain, summarizing what real people " +
  "say online so a mental-health provider can understand their market and clients.\n" +
  "Use ONLY the numbered sources. Synthesize and summarize the themes, complaints, " +
  "needs, and notable quotes. Cite sources like [1], [2].\n" +
  "Write in clean plain text. Do not use Markdown symbols like ### or **bold**. " +
  "Do not add hashtags or emojis unless the user explicitly asks for them.\n" +
  "Only say you don't have enough information if the sources are genuinely unrelated " +
  "to the question. Do not invent facts beyond the sources.";

const BOOKS_CONTENT_PROMPT =
  "You are the Greater Change Health book-to-content strategist.\n" +
  "Your job is to turn therapy/psychology book sources into sharp, original organic " +
  "social content ideas for GCH. Think like a senior mental-health content creator " +
  "and brand strategist, not a generic wellness caption writer.\n\n" +
  "Use ONLY the numbered book sources for the underlying ideas. Cite sources like [1], [2]. " +
  "Do not invent book claims. Do not quote long passages; paraphrase the insight and only " +
  "use very short source phrases when truly useful.\n\n" +
  "Make the output specific and usable. Prefer fresh angles, hooks, carousels, short video " +
  "scripts, founder POV posts, and contrarian but responsible takes. Tie ideas back to GCH's " +
  "brand: accessible therapy, emotional literacy, practical help, trust, and human connection.\n\n" +
  "Write in clean plain text. Do not use Markdown symbols like ### or **bold**. Use simple labels " +
  "such as Slide 1, Hook, Visual, Caption, Why it works. Do not add hashtags or emojis unless " +
  "the user explicitly asks for them.\n\n" +
  "Avoid generic wellness language, vague hashtags, empty inspirational captions, emoji-heavy " +
  "copy, or saying only 'be vulnerable' / 'practice empathy' / 'set boundaries' without a concrete " +
  "angle. If the user asks for viral/social content, include: 1) a strong hook, 2) the source insight, " +
  "3) why the audience will care, 4) the post format, and 5) draft copy GCH could actually post.";

const DEFAULT_ANSWER_MODEL = process.env.ANSWER_MODEL || "gpt-4o";
const BOOKS_ANSWER_MODEL = process.env.BOOKS_ANSWER_MODEL || "gpt-4o";
const KPI_ANSWER_MODEL = process.env.KPI_ANSWER_MODEL || "gpt-4o";

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ error: "Use POST" });
    return;
  }
  try {
    // 0. make sure the keys are actually present (clear message if not)
    const missing = ["OPENAI_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_KEY"].filter(
      (k) => !process.env[k]
    );
    if (missing.length) {
      res.status(500).json({
        error:
          "Missing environment variables: " +
          missing.join(", ") +
          ". Add them in Vercel (vercel env add) and redeploy with 'npx vercel --prod'.",
      });
      return;
    }

    // create clients inside the handler so a config problem returns JSON, not a crash
    const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
    const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY);

    const question = (req.body && req.body.question ? String(req.body.question) : "").trim();
    if (!question) {
      res.status(400).json({ error: "Please include a question." });
      return;
    }

    // which knowledge to search: consumer voice, research, books, competitors, or all
    const source = req.body && req.body.source ? String(req.body.source) : "both";

    // ---- KPI / finance path: PASSWORD-GATED, and answers from numbers not vectors ----
    if (source === "kpis") {
      const passcode = req.body && req.body.passcode ? String(req.body.passcode) : "";
      if (!process.env.KPI_PASSCODE || passcode !== process.env.KPI_PASSCODE) {
        res.status(401).json({ error: "Locked. Enter the finance passcode to view KPIs." });
        return;
      }
      const { data: rows, error: kErr } = await supabase
        .from("kpi_snapshot")
        .select("metric,value,period,source")
        .order("period", { ascending: false })
        .limit(200);
      if (kErr) throw new Error("Supabase: " + kErr.message);
      if (!rows || rows.length === 0) {
        res.status(200).json({ answer: "No KPI data yet. Run ingest_stripe.py first.", sources: [] });
        return;
      }
      const table =
        "metric,value,period,source\n" +
        rows.map((r) => `${r.metric},${r.value},${r.period},${r.source}`).join("\n");
      const kpiResp = await openai.chat.completions.create({
        model: KPI_ANSWER_MODEL,
        max_tokens: 700,
        messages: [
          {
            role: "system",
            content:
              "You are the Greater Change Health finance brain. Answer using ONLY the KPI " +
              "table (CSV). Do the math when asked (growth, ratios). Be precise and state the " +
              "period. If it's not in the data, say so. Do not invent numbers.",
          },
          { role: "user", content: `KPI TABLE (CSV):\n${table}\n\nQuestion: ${question}` },
        ],
      });
      res.status(200).json({ answer: kpiResp.choices[0].message.content, sources: [] });
      return;
    }

    const { evidence, debug } = await retrieveEvidence({
      openai,
      supabase,
      query: question,
      source,
    });

    if (!evidence.length) {
      res.status(200).json({
        answer: "The brain is empty. Run ingest.py to fill it, then ask again.",
        sources: [],
        debug: req.body && req.body.debug ? debug : undefined,
      });
      return;
    }

    // Build compressed, numbered evidence. The final model may cite only these IDs.
    const context = evidence
      .map(
        (e, i) =>
          `[EVIDENCE ${i + 1}]\n` +
          `Source type: ${e.sourceType || "unknown"}\n` +
          `URL: ${e.sourceUrl || "no link"}\n` +
          `Text: ${e.text}`
      )
      .join("\n\n");

    const answerPrompt = source === "books" ? BOOKS_CONTENT_PROMPT : SYSTEM_PROMPT;
    const userPrompt =
      source === "books"
        ? `Book evidence:\n${context}\n\nContent request: ${question}\n\nCreate GCH-ready social content. Cite evidence like [1], [2].`
        : `Evidence:\n${context}\n\nQuestion: ${question}\n\nCite evidence like [1], [2].`;

    const resp = await openai.chat.completions.create({
      model: source === "books" ? BOOKS_ANSWER_MODEL : DEFAULT_ANSWER_MODEL,
      max_tokens: source === "books" ? 1300 : 900,
      messages: [
        { role: "system", content: answerPrompt },
        { role: "user", content: userPrompt },
      ],
    });

    res.status(200).json({
      answer: resp.choices[0].message.content,
      sources: evidence.map((e) => ({
        subreddit: e.subreddit || null,
        url: e.sourceUrl || null,
        sourceType: e.sourceType || null,
      })),
      debug: req.body && req.body.debug ? debug : undefined,
    });
  } catch (e) {
    res.status(500).json({ error: String((e && e.message) || e) });
  }
}

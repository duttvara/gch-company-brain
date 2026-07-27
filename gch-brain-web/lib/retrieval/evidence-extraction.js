import { RETRIEVAL_MODELS, USE_LLM_EXTRACTION } from "./config.js";

function sentenceFallback(content, maxChars = 900) {
  return String(content || "").replace(/\s+/g, " ").trim().slice(0, maxChars);
}

function queryTerms(query) {
  return new Set(
    String(query || "")
      .toLowerCase()
      .split(/[^a-z0-9]+/)
      .filter((term) => term.length > 3)
  );
}

function localEvidenceText(content, query, maxChars = 850) {
  const terms = queryTerms(query);
  const sentences = String(content || "")
    .replace(/\s+/g, " ")
    .split(/(?<=[.!?])\s+/)
    .map((sentence) => sentence.trim())
    .filter(Boolean);

  const scored = sentences.map((sentence, i) => {
    const lower = sentence.toLowerCase();
    let score = 0;
    for (const term of terms) if (lower.includes(term)) score += 1;
    return { sentence, i, score };
  });

  const selected = scored
    .filter((row) => row.score > 0)
    .sort((a, b) => b.score - a.score || a.i - b.i)
    .slice(0, 4)
    .sort((a, b) => a.i - b.i)
    .map((row) => row.sentence)
    .join(" ");

  return (selected || sentenceFallback(content, maxChars)).slice(0, maxChars);
}

function parseItems(text) {
  try {
    const parsed = JSON.parse(text);
    return Array.isArray(parsed.items) ? parsed.items : [];
  } catch {
    return [];
  }
}

export async function extractEvidenceSpans(openai, query, mode, candidates) {
  if (!candidates.length) return { evidence: [], used: false };
  if (!USE_LLM_EXTRACTION) {
    return {
      used: true,
      method: "local_sentence",
      evidence: candidates.map((candidate) => toEvidenceSpan(candidate, localEvidenceText(candidate.content, query))),
    };
  }

  try {
    const sources = candidates.map((candidate, i) => ({
      id: candidate.chunkId,
      n: i + 1,
      text: candidate.content.slice(0, 3500),
    }));
    const resp = await openai.chat.completions.create({
      model: RETRIEVAL_MODELS.extract,
      temperature: 0,
      max_tokens: 1400,
      response_format: { type: "json_object" },
      messages: [
        {
          role: "system",
          content:
            "Extract exact source sentences for RAG evidence. Return strict JSON: " +
            "{\"items\":[{\"id\":\"chunk id\",\"spans\":[{\"text\":\"exact source sentence or connected sentences\"}]}]}. " +
            "Do not paraphrase. Use empty spans if a source does not directly help.",
        },
        {
          role: "user",
          content: `Mode: ${mode}\nQuery: ${query}\n\nSources:\n${JSON.stringify(sources)}`,
        },
      ],
    });
    const items = parseItems(resp.choices[0].message.content);
    const spansById = new Map(items.map((item) => [String(item.id), item.spans || []]));
    return {
      used: true,
      method: "llm",
      evidence: candidates.map((candidate) => {
        const spans = (spansById.get(candidate.chunkId) || [])
          .map((span) => String(span.text || "").trim())
          .filter((span) => span && candidate.content.includes(span));
        const text = spans.length ? spans.join(" ") : sentenceFallback(candidate.content);
        return toEvidenceSpan(candidate, text);
      }),
    };
  } catch (error) {
    console.error("Evidence extraction fallback:", error.message);
    return {
      used: false,
      method: "fallback_truncated_chunk",
      evidence: candidates.map((candidate) => toEvidenceSpan(candidate, sentenceFallback(candidate.content))),
    };
  }
}

function toEvidenceSpan(candidate, text) {
  const startOffset = candidate.content.indexOf(text);
  return {
    chunkId: candidate.chunkId,
    documentId: candidate.documentId,
    text,
    title: candidate.title,
    sourceUrl: candidate.sourceUrl,
    sourceType: candidate.sourceType,
    subreddit: candidate.subreddit,
    startOffset: startOffset >= 0 ? startOffset : null,
    endOffset: startOffset >= 0 ? startOffset + text.length : null,
    fusedScore: candidate.fusedScore,
    rerankerScore: candidate.rerankerScore ?? null,
    vectorRank: candidate.vectorRank,
    fullTextRank: candidate.fullTextRank,
    metadata: candidate.metadata || {},
  };
}

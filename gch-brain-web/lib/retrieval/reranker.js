import { MODE_RERANKING_HINTS, RETRIEVAL_MODELS } from "./config.js";

function safeJsonArray(text) {
  try {
    const parsed = JSON.parse(text);
    return Array.isArray(parsed) ? parsed : parsed.results || [];
  } catch {
    const match = String(text || "").match(/\[[\s\S]*\]/);
    if (!match) return [];
    try {
      return JSON.parse(match[0]);
    } catch {
      return [];
    }
  }
}

export async function rerankCandidates(openai, query, mode, candidates) {
  if (!candidates.length) return { candidates, used: false };

  const compactCandidates = candidates.map((candidate, i) => ({
    id: candidate.chunkId,
    n: i + 1,
    source: candidate.sourceUrl,
    text: candidate.content.slice(0, 1400),
  }));

  try {
    const resp = await openai.chat.completions.create({
      model: RETRIEVAL_MODELS.rerank,
      temperature: 0,
      max_tokens: 900,
      response_format: { type: "json_object" },
      messages: [
        {
          role: "system",
          content:
            "You rerank retrieved passages for a RAG system. Return strict JSON: " +
            "{\"results\":[{\"id\":\"chunk id\",\"score\":0-10}]}. Score direct usefulness for the query. " +
            (MODE_RERANKING_HINTS[mode] || ""),
        },
        {
          role: "user",
          content: `Query: ${query}\n\nCandidates:\n${JSON.stringify(compactCandidates)}`,
        },
      ],
    });
    const scores = new Map(
      safeJsonArray(resp.choices[0].message.content).map((row) => [String(row.id), Number(row.score) || 0])
    );
    return {
      used: true,
      candidates: candidates
        .map((candidate) => ({
          ...candidate,
          rerankerScore: scores.get(candidate.chunkId) ?? 0,
        }))
        .sort((a, b) => (b.rerankerScore ?? 0) - (a.rerankerScore ?? 0) || b.fusedScore - a.fusedScore),
    };
  } catch (error) {
    console.error("Retrieval reranking skipped:", error.message);
    return { candidates, used: false };
  }
}

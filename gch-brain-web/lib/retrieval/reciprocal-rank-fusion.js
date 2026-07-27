import { RRF_K } from "./config.js";

export function calculateWeightedRRFScore({
  vectorRank,
  fullTextRank,
  vectorWeight,
  fullTextWeight,
  k = RRF_K,
}) {
  const vectorContribution =
    vectorRank !== undefined ? vectorWeight * (1 / (k + vectorRank)) : 0;
  const fullTextContribution =
    fullTextRank !== undefined ? fullTextWeight * (1 / (k + fullTextRank)) : 0;
  return vectorContribution + fullTextContribution;
}

export function mergeWithWeightedRRF(vectorResults, fullTextResults, config) {
  const byId = new Map();

  function upsert(row, rank, kind) {
    const chunkId = row.id || row.chunk_id;
    if (!chunkId) return;
    const existing = byId.get(chunkId) || {
      chunkId,
      documentId: row.parent_id || row.source_url || chunkId,
      content: row.content || "",
      title: row.title || row.source_url || null,
      sourceUrl: row.source_url || null,
      sourceType: row.source_type || null,
      subreddit: row.subreddit || null,
      metadata: {},
    };
    if (kind === "vector") {
      existing.vectorRank = rank;
      existing.vectorScore = row.similarity ?? row.hybrid_score ?? null;
    } else {
      existing.fullTextRank = rank;
      existing.fullTextScore = row.rank ?? row.keyword_rank ?? null;
    }
    byId.set(chunkId, existing);
  }

  vectorResults.forEach((row, i) => upsert(row, i + 1, "vector"));
  fullTextResults.forEach((row, i) => upsert(row, i + 1, "fullText"));

  return [...byId.values()]
    .map((candidate) => ({
      ...candidate,
      fusedScore: calculateWeightedRRFScore({
        vectorRank: candidate.vectorRank,
        fullTextRank: candidate.fullTextRank,
        vectorWeight: config.vectorWeight,
        fullTextWeight: config.fullTextWeight,
      }),
    }))
    .sort((a, b) => b.fusedScore - a.fusedScore);
}

import { MODE_RETRIEVAL_CONFIG, SOURCE_FILTERS, SOURCE_TO_MODE } from "./config.js";
import { expandQuery } from "./query-expansion.js";
import { embedQuery, runFullTextSearch, runVectorSearch } from "./search.js";
import { mergeWithWeightedRRF } from "./reciprocal-rank-fusion.js";
import { removeExactDuplicates, removeNearDuplicates } from "./deduplication.js";
import { rerankCandidates } from "./reranker.js";
import { applySourceDiversity } from "./source-diversity.js";
import { extractEvidenceSpans } from "./evidence-extraction.js";

function nowMs() {
  return Date.now();
}

function isOpenAIQuotaError(error) {
  const message = String(error && error.message ? error.message : error).toLowerCase();
  const code = String(error && error.code ? error.code : "").toLowerCase();
  return (
    code === "credit_balance_exhausted" ||
    code === "insufficient_quota" ||
    message.includes("credit_balance_exhausted") ||
    message.includes("insufficient_quota") ||
    message.includes("no credits remaining")
  );
}

export async function retrieveEvidence({ openai, supabase, query, source }) {
  const mode = SOURCE_TO_MODE[source] || SOURCE_TO_MODE.both;
  const config = MODE_RETRIEVAL_CONFIG[mode];
  const filterSources = SOURCE_FILTERS[source] ?? null;
  const started = nowMs();
  const timings = {};
  const expandedQueries = expandQuery(query, mode);
  const lexicalQuery = expandedQueries[expandedQueries.length - 1] || query;

  const vectorStarted = nowMs();
  const vectorPromise = embedQuery(openai, query)
    .then((vector) => runVectorSearch(supabase, vector, config, filterSources))
    .catch((error) => {
      if (isOpenAIQuotaError(error)) {
        throw new Error(
          "OpenAI credits are exhausted, so the app cannot create the search embedding. Add credits in OpenAI billing, then try again."
        );
      }
      console.error("Vector search failed:", error.message);
      return [];
    })
    .finally(() => {
      timings.vectorSearchMs = nowMs() - vectorStarted;
    });

  const fullTextStarted = nowMs();
  const fullTextPromise = runFullTextSearch(supabase, lexicalQuery, config, filterSources)
    .catch((error) => {
      console.error("Full-text search failed:", error.message);
      return [];
    })
    .finally(() => {
      timings.fullTextSearchMs = nowMs() - fullTextStarted;
    });

  const [vectorResults, fullTextResults] = await Promise.all([vectorPromise, fullTextPromise]);
  if (!vectorResults.length && !fullTextResults.length) {
    return {
      evidence: [],
      debug: buildDebug({
        mode,
        query,
        expandedQueries,
        config,
        timings,
        vectorResults,
        fullTextResults,
        merged: [],
        deduped: [],
        reranked: [],
        finalCandidates: [],
        rerankingUsed: false,
        extractionUsed: false,
        started,
      }),
    };
  }

  const mergeStarted = nowMs();
  const merged = mergeWithWeightedRRF(vectorResults, fullTextResults, config);
  timings.mergeMs = nowMs() - mergeStarted;

  const dedupeStarted = nowMs();
  const deduped = removeNearDuplicates(removeExactDuplicates(merged));
  timings.deduplicationMs = nowMs() - dedupeStarted;

  const rerankStarted = nowMs();
  const rerankInput = deduped.slice(0, config.rerankCandidateLimit);
  const rerankedResult = await rerankCandidates(openai, query, mode, rerankInput);
  const reranked = rerankedResult.candidates;
  timings.rerankingMs = nowMs() - rerankStarted;

  const finalCandidates = applySourceDiversity(reranked, config);

  const extractStarted = nowMs();
  const extracted = await extractEvidenceSpans(openai, query, mode, finalCandidates);
  timings.extractionMs = nowMs() - extractStarted;

  return {
    evidence: extracted.evidence,
    debug: buildDebug({
      mode,
      query,
      expandedQueries,
      config,
      timings,
      vectorResults,
      fullTextResults,
      merged,
      deduped,
      reranked,
      finalCandidates,
      rerankingUsed: rerankedResult.used,
      extractionUsed: extracted.used,
      extractionMethod: extracted.method,
      started,
    }),
  };
}

function buildDebug({
  mode,
  query,
  expandedQueries,
  config,
  timings,
  vectorResults,
  fullTextResults,
  merged,
  deduped,
  reranked,
  finalCandidates,
  rerankingUsed,
  extractionUsed,
  extractionMethod,
  started,
}) {
  return {
    mode,
    originalQuery: query,
    expandedQueries,
    vectorWeight: config.vectorWeight,
    fullTextWeight: config.fullTextWeight,
    vectorCandidateCount: vectorResults.length,
    fullTextCandidateCount: fullTextResults.length,
    mergedCandidateCount: merged.length,
    deduplicatedCandidateCount: deduped.length,
    rerankedCandidateCount: reranked.length,
    finalEvidenceCount: finalCandidates.length,
    vectorSearchMs: timings.vectorSearchMs || 0,
    fullTextSearchMs: timings.fullTextSearchMs || 0,
    mergeMs: timings.mergeMs || 0,
    deduplicationMs: timings.deduplicationMs || 0,
    rerankingMs: timings.rerankingMs || 0,
    extractionMs: timings.extractionMs || 0,
    totalRetrievalMs: nowMs() - started,
    rerankingUsed,
    extractionUsed,
    extractionMethod: extractionMethod || null,
    topEvidence: finalCandidates.map((candidate) => ({
      sourceUrl: candidate.sourceUrl,
      sourceType: candidate.sourceType,
      vectorRank: candidate.vectorRank,
      fullTextRank: candidate.fullTextRank,
      fusedScore: Number(candidate.fusedScore.toFixed(5)),
      rerankerScore: candidate.rerankerScore ?? null,
    })),
  };
}

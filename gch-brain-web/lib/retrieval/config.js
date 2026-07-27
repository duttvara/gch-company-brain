export const SOURCE_TO_MODE = {
  both: "consumer_insight",
  consumer: "consumer_insight",
  research: "research_synthesis",
  books: "book_content_strategy",
  b2b: "competitor_analysis",
};

export const SOURCE_FILTERS = {
  both: null,
  consumer: ["reddit"],
  research: ["research"],
  books: ["pdf"],
  b2b: ["b2b"],
};

export const MODE_RETRIEVAL_CONFIG = {
  consumer_insight: {
    vectorWeight: 0.65,
    fullTextWeight: 0.35,
    vectorCandidateLimit: 20,
    fullTextCandidateLimit: 18,
    rerankCandidateLimit: 12,
    finalEvidenceLimit: 6,
    maxChunksPerDocument: 2,
    maxChunksPerDomain: 3,
  },
  research_synthesis: {
    vectorWeight: 0.75,
    fullTextWeight: 0.25,
    vectorCandidateLimit: 24,
    fullTextCandidateLimit: 16,
    rerankCandidateLimit: 14,
    finalEvidenceLimit: 6,
    maxChunksPerDocument: 2,
    maxChunksPerDomain: 4,
  },
  book_content_strategy: {
    vectorWeight: 0.7,
    fullTextWeight: 0.3,
    vectorCandidateLimit: 24,
    fullTextCandidateLimit: 18,
    rerankCandidateLimit: 14,
    finalEvidenceLimit: 6,
    maxChunksPerDocument: 3,
    maxChunksPerDomain: 4,
  },
  competitor_analysis: {
    vectorWeight: 0.4,
    fullTextWeight: 0.6,
    vectorCandidateLimit: 18,
    fullTextCandidateLimit: 24,
    rerankCandidateLimit: 12,
    finalEvidenceLimit: 6,
    maxChunksPerDocument: 2,
    maxChunksPerDomain: 3,
  },
};

export const MODE_RERANKING_HINTS = {
  consumer_insight:
    "Prioritize direct user experiences, pain points, behavioral evidence, and detailed explanations.",
  research_synthesis:
    "Prioritize specific findings, systematic reviews, methods, sample details, and evidence over broad claims.",
  book_content_strategy:
    "Prioritize explicit frameworks, memorable examples, content-worthy arguments, and passages tied to the requested theme.",
  competitor_analysis:
    "Prioritize official product pages, exact feature descriptions, pricing, employer program details, and specific comparison evidence.",
};

export const RETRIEVAL_MODELS = {
  rerank: process.env.RERANK_MODEL || "gpt-4o-mini",
  extract: process.env.EXTRACT_MODEL || "gpt-4o-mini",
};

export const USE_LLM_EXTRACTION = process.env.USE_LLM_EXTRACTION === "true";
export const RRF_K = 60;

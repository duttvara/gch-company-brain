import { createHash } from "node:crypto";

export function normaliseContentForHash(content) {
  return String(content || "").toLowerCase().replace(/\s+/g, " ").trim();
}

export function contentHash(content) {
  return createHash("sha256").update(normaliseContentForHash(content)).digest("hex");
}

export function removeExactDuplicates(candidates) {
  const byHash = new Map();
  for (const candidate of candidates) {
    const hash = contentHash(candidate.content);
    const existing = byHash.get(hash);
    if (!existing || candidate.fusedScore > existing.fusedScore) byHash.set(hash, candidate);
  }
  return [...byHash.values()].sort((a, b) => b.fusedScore - a.fusedScore);
}

function tokenSet(text) {
  return new Set(
    normaliseContentForHash(text)
      .split(/[^a-z0-9]+/)
      .filter((token) => token.length > 3)
  );
}

function tokenOverlap(a, b) {
  const aTokens = tokenSet(a);
  const bTokens = tokenSet(b);
  if (!aTokens.size || !bTokens.size) return 0;
  let shared = 0;
  for (const token of aTokens) if (bTokens.has(token)) shared += 1;
  return shared / Math.min(aTokens.size, bTokens.size);
}

export function removeNearDuplicates(candidates, threshold = 0.82) {
  const kept = [];
  for (const candidate of candidates) {
    const sameSourceDuplicate = kept.some((other) => {
      const sameSource = other.sourceUrl && candidate.sourceUrl && other.sourceUrl === candidate.sourceUrl;
      return sameSource && tokenOverlap(other.content, candidate.content) >= threshold;
    });
    if (!sameSourceDuplicate) kept.push(candidate);
  }
  return kept;
}

import test from "node:test";
import assert from "node:assert/strict";
import { calculateWeightedRRFScore, mergeWithWeightedRRF } from "../lib/retrieval/reciprocal-rank-fusion.js";
import { normaliseContentForHash, removeExactDuplicates, removeNearDuplicates } from "../lib/retrieval/deduplication.js";
import { applySourceDiversity } from "../lib/retrieval/source-diversity.js";
import { expandQuery } from "../lib/retrieval/query-expansion.js";

test("weighted RRF rewards results found by both retrievers", () => {
  const both = calculateWeightedRRFScore({
    vectorRank: 3,
    fullTextRank: 3,
    vectorWeight: 0.5,
    fullTextWeight: 0.5,
  });
  const one = calculateWeightedRRFScore({
    vectorRank: 1,
    vectorWeight: 0.5,
    fullTextWeight: 0.5,
  });
  assert.ok(both > one);
});

test("mode weights change merged ranking influence", () => {
  const vectorResults = [{ id: "generic", content: "therapy platform", similarity: 0.9 }];
  const fullTextResults = [{ id: "exact", content: "BetterHelp pricing", rank: 0.8 }];
  const competitorConfig = { vectorWeight: 0.4, fullTextWeight: 0.6 };
  const researchConfig = { vectorWeight: 0.75, fullTextWeight: 0.25 };

  assert.equal(mergeWithWeightedRRF(vectorResults, fullTextResults, competitorConfig)[0].chunkId, "exact");
  assert.equal(mergeWithWeightedRRF(vectorResults, fullTextResults, researchConfig)[0].chunkId, "generic");
});

test("normalization removes case and repeated whitespace", () => {
  assert.equal(normaliseContentForHash("  Hello   WORLD "), "hello world");
});

test("exact duplicate removal keeps stronger candidate", () => {
  const deduped = removeExactDuplicates([
    { chunkId: "a", content: "Same content", fusedScore: 0.1 },
    { chunkId: "b", content: " same   CONTENT ", fusedScore: 0.2 },
  ]);
  assert.equal(deduped.length, 1);
  assert.equal(deduped[0].chunkId, "b");
});

test("near duplicate removal only collapses same source overlap", () => {
  const candidates = [
    { chunkId: "a", sourceUrl: "https://example.com/a", content: "one two three four five six seven", fusedScore: 0.2 },
    { chunkId: "b", sourceUrl: "https://example.com/a", content: "one two three four five six seven extra", fusedScore: 0.1 },
    { chunkId: "c", sourceUrl: "https://other.com/a", content: "one two three four five six seven", fusedScore: 0.05 },
  ];
  const deduped = removeNearDuplicates(candidates, 0.8);
  assert.deepEqual(deduped.map((c) => c.chunkId), ["a", "c"]);
});

test("source diversity enforces document and domain limits", () => {
  const selected = applySourceDiversity(
    [
      { chunkId: "1", documentId: "doc1", sourceUrl: "https://a.com/1" },
      { chunkId: "2", documentId: "doc1", sourceUrl: "https://a.com/2" },
      { chunkId: "3", documentId: "doc1", sourceUrl: "https://a.com/3" },
      { chunkId: "4", documentId: "doc2", sourceUrl: "https://b.com/1" },
    ],
    { maxChunksPerDocument: 2, maxChunksPerDomain: 3, finalEvidenceLimit: 4 }
  );
  assert.deepEqual(selected.map((c) => c.chunkId), ["1", "2", "4"]);
});

test("query expansion preserves original query and adds domain terms", () => {
  const expanded = expandQuery("Why is employee engagement low?", "competitor_analysis");
  assert.equal(expanded[0], "Why is employee engagement low?");
  assert.match(expanded[1], /utilization|utilisation/);
  assert.match(expanded[1], /EAP/);
});

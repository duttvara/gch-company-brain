function domainFromUrl(url) {
  if (!url) return "unknown";
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function applySourceDiversity(candidates, config) {
  const perDocument = new Map();
  const perDomain = new Map();
  const selected = [];

  for (const candidate of candidates) {
    const docKey = candidate.documentId || candidate.sourceUrl || candidate.chunkId;
    const domainKey = domainFromUrl(candidate.sourceUrl);
    const docCount = perDocument.get(docKey) || 0;
    const domainCount = perDomain.get(domainKey) || 0;

    if (docCount >= config.maxChunksPerDocument) continue;
    if (domainCount >= config.maxChunksPerDomain) continue;

    selected.push(candidate);
    perDocument.set(docKey, docCount + 1);
    perDomain.set(domainKey, domainCount + 1);
    if (selected.length >= config.finalEvidenceLimit) break;
  }

  return selected;
}

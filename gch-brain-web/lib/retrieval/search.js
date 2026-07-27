export async function embedQuery(openai, query) {
  const emb = await openai.embeddings.create({
    model: "text-embedding-3-small",
    input: query,
  });
  return emb.data[0].embedding;
}

export async function runVectorSearch(supabase, vector, config, filterSources) {
  const result = await supabase.rpc("match_documents", {
    query_embedding: JSON.stringify(vector),
    match_count: config.vectorCandidateLimit,
    filter_sources: filterSources,
  });
  if (result.error) throw new Error(result.error.message);
  return result.data || [];
}

export async function runFullTextSearch(supabase, queryText, config, filterSources) {
  const result = await supabase.rpc("match_documents_full_text", {
    query_text: queryText,
    match_count: config.fullTextCandidateLimit,
    filter_sources: filterSources,
  });
  if (result.error) throw new Error(result.error.message);
  return result.data || [];
}

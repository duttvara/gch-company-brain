const DOMAIN_SYNONYMS = {
  therapy: ["counselling", "counseling", "psychotherapy", "mental health support"],
  therapist: ["provider", "clinician", "counselor", "counsellor"],
  engagement: ["utilisation", "utilization", "usage", "adoption", "participation", "retention"],
  employee: ["worker", "staff", "workforce", "team member"],
  workplace: ["employer", "company", "organization", "organisation", "EAP", "employee assistance program"],
  eap: ["employee assistance program", "employee assistance programme", "workplace therapy"],
  churn: ["retention", "cancellation", "dropoff", "renewal", "staying"],
  revenue: ["MRR", "ARR", "gross volume", "billing", "subscription"],
  atlas: ["Atlas of the Heart", "Brene Brown", "Brené Brown", "emotional literacy"],
  competitor: ["BetterHelp", "Talkspace", "Lyra Health", "Spring Health", "Modern Health", "Headspace"],
};

export function expandQuery(query, mode) {
  const lower = query.toLowerCase();
  const additions = [];

  for (const [term, synonyms] of Object.entries(DOMAIN_SYNONYMS)) {
    if (lower.includes(term)) additions.push(...synonyms);
  }

  if (mode === "competitor_analysis") additions.push("pricing", "features", "employer", "EAP");
  if (mode === "research_synthesis") additions.push("study", "trial", "systematic review", "outcomes");
  if (mode === "book_content_strategy") additions.push("framework", "chapter", "concept", "example");

  const expanded = [query, ...new Set(additions)].join(" ");
  return [...new Set([query, expanded].filter(Boolean))];
}

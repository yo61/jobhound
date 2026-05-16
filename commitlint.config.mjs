export default {
  extends: ['@commitlint/config-conventional'],
  rules: {
    // Allow class names and acronyms in subjects (e.g. "OpportunityQuery uses",
    // "MCP tools use", "Slug.build accepts"). The default conventional ruleset
    // rejects pascal-case/start-case/sentence-case/upper-case subjects, which
    // is too restrictive for domain-rich code where the natural subject word is
    // a class or initialism.
    'subject-case': [0],
  },
};

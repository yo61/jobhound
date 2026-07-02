export default {
  extends: ['@commitlint/config-conventional'],
  // Dependabot auto-generates commit bodies with long markdown URLs that exceed
  // body-max-line-length. It won't wrap them, so skip linting its commits while
  // keeping the full ruleset enforced for human authors.
  ignores: [(message) => message.includes('Signed-off-by: dependabot[bot]')],
  rules: {
    // Allow class names and acronyms in subjects (e.g. "OpportunityQuery uses",
    // "MCP tools use", "Slug.build accepts"). The default conventional ruleset
    // rejects pascal-case/start-case/sentence-case/upper-case subjects, which
    // is too restrictive for domain-rich code where the natural subject word is
    // a class or initialism.
    'subject-case': [0],
  },
};

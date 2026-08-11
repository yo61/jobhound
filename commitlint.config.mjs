export default {
  extends: ['@commitlint/config-conventional'],
  // Dependabot auto-generates commit bodies with long markdown URLs that exceed
  // body-max-line-length. It won't wrap them, so skip linting its commits while
  // keeping the full ruleset enforced for human authors.
  ignores: [(message) => message.includes('Signed-off-by: dependabot[bot]')],
  rules: {
    // `deps` is not a config-conventional type. Dependabot is configured
    // to use it so release-please can route those commits to a
    // Dependencies changelog section -- sections are keyed by type, and
    // the default `chore(deps)` lands under the hidden `chore` type.
    'type-enum': [
      2,
      'always',
      [
        'build',
        'chore',
        'ci',
        'deps',
        'docs',
        'feat',
        'fix',
        'perf',
        'refactor',
        'revert',
        'style',
        'test',
      ],
    ],
    // Allow class names and acronyms in subjects (e.g. "OpportunityQuery uses",
    // "MCP tools use", "Slug.build accepts"). The default conventional ruleset
    // rejects pascal-case/start-case/sentence-case/upper-case subjects, which
    // is too restrictive for domain-rich code where the natural subject word is
    // a class or initialism.
    'subject-case': [0],
  },
};

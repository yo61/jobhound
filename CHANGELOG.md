# Changelog

## [0.5.0](https://github.com/yo61/jobhound/compare/v0.4.0...v0.5.0) (2026-05-14)


### Features

* **application:** add field_service for single-field setters ([d434938](https://github.com/yo61/jobhound/commit/d4349388deb1ebec864b1a79ba85b382cf999d24))
* **application:** add lifecycle_service for state-transition orchestration ([98a734e](https://github.com/yo61/jobhound/commit/98a734e8a77fdc2619e41191e5101da177d820a4))
* **application:** add ops_service for notes/archive/delete/sync ([7965c82](https://github.com/yo61/jobhound/commit/7965c82d547501aee2ba06d10bbf6c4311fffd80))
* **application:** add relation_service for tags/contacts/links ([d2e45e2](https://github.com/yo61/jobhound/commit/d2e45e24e57a29543360027356d417a95bf49891))
* **application:** thread no_commit through lifecycle_service functions ([254d2e3](https://github.com/yo61/jobhound/commit/254d2e30213f28061273fd6aed623b8b663ed6b1))
* **cli:** register jh mcp subcommand ([aa6385a](https://github.com/yo61/jobhound/commit/aa6385a3d89cd55f3bb49aba36d338b68e98d505))
* **domain:** carry structured candidates/query on slug exceptions ([fb0ed0e](https://github.com/yo61/jobhound/commit/fb0ed0e7c88ea4b8492840c64a05bf1b796c2138))
* **mcp:** add converters (compute_diff + mutation_response) ([07f7fe2](https://github.com/yo61/jobhound/commit/07f7fe29983866cd0b709e337fdb4cadd06afd27))
* **mcp:** add error mapping + extend InvalidTransitionError with structured fields ([5789c2a](https://github.com/yo61/jobhound/commit/5789c2a1df98ae0a2991e6519135a379e1ecbc3a))
* **mcp:** add field tools (set_company/role/priority/status/...; touch) ([8a36c18](https://github.com/yo61/jobhound/commit/8a36c1833b3e1d9ab2713c3ffca26d8288930160))
* **mcp:** add lifecycle tools (new/apply/log/withdraw/ghost/accept/decline) ([98283cd](https://github.com/yo61/jobhound/commit/98283cd0d320a2f48a57123669dc578f93b75343))
* **mcp:** add ops tools (add_note/archive/delete/sync) ([15873bb](https://github.com/yo61/jobhound/commit/15873bb99a114e2a68a6d57575f56471b04e7cdb))
* **mcp:** add read tools (list/get/stats/files/read_file) ([b588cd7](https://github.com/yo61/jobhound/commit/b588cd7960c797f0381c8571ca73e618132efd73))
* **mcp:** add relation tools (add_tag/remove_tag/add_contact/set_link) ([10a3ce5](https://github.com/yo61/jobhound/commit/10a3ce53b235ac9fcf1c5125d82c859e88f2e576))
* **mcp:** scaffold FastMCP server with lazy SDK import ([f4fee10](https://github.com/yo61/jobhound/commit/f4fee10a863a8511de6380898acd2d4af286c672))


### Bug Fixes

* **phase4:** address final-review findings ([b90fdaa](https://github.com/yo61/jobhound/commit/b90fdaa0d3ccbec0a6116f18db690ae0bacb4c9c))


### Documentation

* add phase 4 implementation plan ([7dc5ba3](https://github.com/yo61/jobhound/commit/7dc5ba3e47f81760bfe8054ed5702ad7236ad2d0))
* document jh mcp + uvx jh-mcp install paths ([e935add](https://github.com/yo61/jobhound/commit/e935add17e9ae35d56d7733e5400fd81f0b1f67f))
* spec phase 4 MCP server design ([8d08096](https://github.com/yo61/jobhound/commit/8d080960beba5abd4572068bdbf7beed9dceb074))
* tighten phase 4 spec on DDD layering ([db60aa1](https://github.com/yo61/jobhound/commit/db60aa113c634a46886214577fc644cacd1f3b8d))

## [0.4.0](https://github.com/yo61/jobhound/compare/v0.3.0...v0.4.0) (2026-05-13)


### Features

* **application:** add JSON converters for snapshots and stats ([99432bb](https://github.com/yo61/jobhound/commit/99432bb7c8bd1e0ceabd2d19fbfe9043a4d4c292))
* **application:** add list_envelope and show_envelope builders ([f969be6](https://github.com/yo61/jobhound/commit/f969be611f2548e9fb84937862b02392db725438))
* **application:** add OpportunityQuery.files and .read_file with traversal guard ([4bc2be8](https://github.com/yo61/jobhound/commit/4bc2be89f702fd0ca553b23d7719d9e7e2dc4203))
* **application:** add OpportunityQuery.find and .list with filters ([12dd902](https://github.com/yo61/jobhound/commit/12dd902d32afab6dc091e493f4d17a203dac42bc))
* **application:** add OpportunityQuery.stats with funnel and sources ([d5f4de5](https://github.com/yo61/jobhound/commit/d5f4de582818c3304332e934944a1610a308fce3))
* **application:** add read-side snapshot dataclasses ([11ae52d](https://github.com/yo61/jobhound/commit/11ae52d9d83947bbd9536298a8ca5cbaa4a5ee39))
* **cli:** add jh export command with filter flags ([7a1290d](https://github.com/yo61/jobhound/commit/7a1290de87506af5514828e8d8c5da86a36e8256))
* **cli:** add jh show command with --json output ([a435261](https://github.com/yo61/jobhound/commit/a4352616051317bfc0412cb702279eb36c90b4dd))


### Documentation

* add phase 3a implementation plan ([34531ef](https://github.com/yo61/jobhound/commit/34531efdac0fc8b723d3bedf427b6abee4dda3b9))
* document jh show + jh export and drop phase 3a pickup notes ([0b43074](https://github.com/yo61/jobhound/commit/0b4307450ab8ac62c33a9859712579a5d93ca8e0))
* spec phase 3a read API + DDD reorganisation ([dd09043](https://github.com/yo61/jobhound/commit/dd090438ec05b7e74f20d7035757de3c8d12610b))

## [0.3.0](https://github.com/yo61/jobhound/compare/v0.2.0...v0.3.0) (2026-05-12)


### Features

* lower minimum Python to 3.11 ([2e75e95](https://github.com/yo61/jobhound/commit/2e75e959ac123239b0e31d98224155f5378bc9c7))


### Documentation

* add README for PyPI long description and quick-start usage ([2ba0a42](https://github.com/yo61/jobhound/commit/2ba0a42c9ce48dae77f8172332e5b72e52931ba5))

## [0.2.0](https://github.com/yo61/jobhound/compare/jobhound-v0.1.0...jobhound-v0.2.0) (2026-05-12)


### Features

* add auto-commit helper ([734c1fa](https://github.com/yo61/jobhound/commit/734c1faef8a018bcca459fa22113b92b89f02677))
* add Config loader with XDG-strict paths ([b47bfc5](https://github.com/yo61/jobhound/commit/b47bfc5bcfcaa8fc3dd20468f2ece947a0206cca))
* add jh apply command and transitions module ([5e402a6](https://github.com/yo61/jobhound/commit/5e402a6e37286a10078c1552abbcdfac441e305e))
* add jh archive, delete, sync commands ([ec8423a](https://github.com/yo61/jobhound/commit/ec8423a1f6a7dffef7f927e5cd7d942838a15407))
* add jh edit command with validation loop ([0cddf87](https://github.com/yo61/jobhound/commit/0cddf8781fc1b9ab44d658ca9c469ddd989cda69))
* add jh link and contact commands ([1806566](https://github.com/yo61/jobhound/commit/18065667410be80d6955c327b709d4c09d19c17e))
* add jh list command ([1596f36](https://github.com/yo61/jobhound/commit/1596f3644d2160971a57e6b1628749f588ce0740))
* add jh log command ([5f4d405](https://github.com/yo61/jobhound/commit/5f4d405ee71435e46b57102b34b2a572f9be41ff))
* add jh new command ([85a56b2](https://github.com/yo61/jobhound/commit/85a56b23a26b5f0a74250f8bb190edbadf2816eb))
* add jh note, priority, tag commands ([38daf05](https://github.com/yo61/jobhound/commit/38daf05b82bb58b03c774d16bae0ca259ce4a745))
* add jh withdraw, ghost, accept, decline commands ([5cd852b](https://github.com/yo61/jobhound/commit/5cd852b0a6672b0c17e05dc20edbec501b623a6a))
* add meta.toml read/write/validate ([0f24d65](https://github.com/yo61/jobhound/commit/0f24d651d329893a1c85bf6c7686d9918e5340af))
* add Opportunity dataclass ([8c5f233](https://github.com/yo61/jobhound/commit/8c5f23344de67d21eef97d0a24946508833a72d3))
* add Paths dataclass ([51589c9](https://github.com/yo61/jobhound/commit/51589c9c1fa8b2335eeb904e3a679b622041e16a))
* add prompt helpers and date parser ([936f5bc](https://github.com/yo61/jobhound/commit/936f5bc3d0c8c3a846735d8457aed73a65a9501e))
* add slug resolver ([afc0f2d](https://github.com/yo61/jobhound/commit/afc0f2d123b7d415e412c2086560f8057e5755b1))
* add typer app skeleton and shared test fixture ([2a1c87d](https://github.com/yo61/jobhound/commit/2a1c87df4ee312ec8c209c7b19d7d671ba856651))


### Bug Fixes

* drop None values from opportunity links at parse time ([ea6daa0](https://github.com/yo61/jobhound/commit/ea6daa02bda21115d2e57d13061bfa108ffe7c73))


### Documentation

* add DDD refactor plan ([902d865](https://github.com/yo61/jobhound/commit/902d8651aef6157fe4cd3073c912c89754be362f))
* add history rewrite map and align plan commit counts ([5f1af1b](https://github.com/yo61/jobhound/commit/5f1af1b7aef2014b7b5a3924dcf3d0595b9e7414))
* add jh-cli design spec and implementation plan ([b62b81e](https://github.com/yo61/jobhound/commit/b62b81ec585aef083f0fbd1ca826e5447d0c3a48))
* add post-refactor housekeeping plan ([f7c1145](https://github.com/yo61/jobhound/commit/f7c114528bcc8b7d7c53ba6e67ce3a794f209ae4))
* add semantic release & PyPI publishing design spec ([ac91edb](https://github.com/yo61/jobhound/commit/ac91edb6a623ccb6fd60d889e9de75969fb78b36))
* add semantic release implementation plan ([6d882b6](https://github.com/yo61/jobhound/commit/6d882b65f74f6554b69cadc2339801feeec94674))
* convert remaining plan snippets from typer to cyclopts ([82166b9](https://github.com/yo61/jobhound/commit/82166b9efc6685da232894669d1052b8c8dddacb))
* log DDD refactor decision ([c9a4824](https://github.com/yo61/jobhound/commit/c9a4824222e6dcf61e36b8025f4fbfcbf83361f8))
* log YAML-to-TOML migration decision ([b7141c0](https://github.com/yo61/jobhound/commit/b7141c0955e85a187866fc684913437f7a9eb17c))
* seed quality/criteria.md from DDD refactor review findings ([1e6ecca](https://github.com/yo61/jobhound/commit/1e6ecca833612a3f59fccf55945405aafbe76c67))
* update SHA references after history rewrite ([3b9a4ab](https://github.com/yo61/jobhound/commit/3b9a4ab923d8b940a56c731e02af10ec63793cac))

## Changelog

# Changelog

## [0.8.0](https://github.com/yo61/jobhound/compare/v0.7.2...v0.8.0) (2026-05-16)


### ⚠ BREAKING CHANGES

* 'jh edit' is gone. Use 'jh set <field>' or hand-edit.
* every renamed CLI command and MCP tool. See docs/specs/2026-05-16-command-rename-plan.md for the full table.

### Features

* **cli:** add 10 deferred field setters ([e81a511](https://github.com/yo61/jobhound/commit/e81a511fed2b3611b21c3c50857ffaee7e9b8356))
* **cli:** add jh clear subgroup for nullable fields ([5ced221](https://github.com/yo61/jobhound/commit/5ced221c6c1463ba8b101edb995c1550dcd57143))
* **cli:** jh remove link + remove_link MCP tool ([34595bb](https://github.com/yo61/jobhound/commit/34595bb0ccff52ddba9b81af07be4f20cae07c8c))
* command rename per the locked plan (v0.8.0) ([a99d004](https://github.com/yo61/jobhound/commit/a99d004acf5ff191b614e5e576804471d7f9d6d0))
* jh remove contact + remove_contact MCP tool ([247dbf4](https://github.com/yo61/jobhound/commit/247dbf462827d9b609c046b4142e05ee673bb722))
* remove jh edit command ([1d04bfa](https://github.com/yo61/jobhound/commit/1d04bfa417ef977b77f36c15cecbf2f2ca8028a4))


### Documentation

* terse imperative help text across CLI and MCP ([90b3098](https://github.com/yo61/jobhound/commit/90b3098f39f682438430c22a1d7b27e3d27b4b46))

## [0.7.2](https://github.com/yo61/jobhound/compare/v0.7.1...v0.7.2) (2026-05-16)


### Bug Fixes

* **cli:** suppress traceback for known user-facing exceptions ([bccb643](https://github.com/yo61/jobhound/commit/bccb643301380039e0507ba8747831d703902661))

## [0.7.1](https://github.com/yo61/jobhound/compare/v0.7.0...v0.7.1) (2026-05-16)


### Bug Fixes

* **infrastructure:** reject bare dates in meta.toml with migration prompt ([33572f8](https://github.com/yo61/jobhound/commit/33572f8e4e11e9e639822ef075d1735555258450))

## [0.7.0](https://github.com/yo61/jobhound/compare/v0.6.1...v0.7.0) (2026-05-16)


### ⚠ BREAKING CHANGES

* **application:** every new notes.md line now starts with an ISO 8601 Z-suffix UTC timestamp prefix (whole seconds): '- 2026-05-14T13:42:00Z msg'. Historical lines are left as written.
* **application:** serialize lifecycle fields as Z-suffix datetimes (schema v2)
* **domain:** first_contact, applied_on, last_activity, and next_action_due are now datetime | None (tz-aware UTC). Domain method parameter today: date renamed to now: datetime.

### Features

* **application:** notes.md lines get Z-suffix UTC timestamp prefix ([a77fb21](https://github.com/yo61/jobhound/commit/a77fb215c8a0bb2cf2d818145fc2b37df13162fd))
* **application:** serialize lifecycle fields as Z-suffix datetimes (schema v2) ([045b486](https://github.com/yo61/jobhound/commit/045b486000c1d4200513aa91ac286f8f63da07cf))
* **cli:** add 'jh migrate utc-timestamps' command ([2b305dd](https://github.com/yo61/jobhound/commit/2b305ddbb70e195a2e328f934a8e4c142b3e632e))
* **cli:** commands accept datetime flags via cyclopts native parsing ([fcd83d6](https://github.com/yo61/jobhound/commit/fcd83d69dcb42a88c56d2308c2d0b45c7df4dfee))
* **deps:** add tzlocal for local-zone awareness ([d5557ea](https://github.com/yo61/jobhound/commit/d5557ea65982a55cab5fe3ef6fa94100951ea273))
* **domain:** add timekeeping module for UTC/local conversion ([56a799c](https://github.com/yo61/jobhound/commit/56a799ce9a55b1f46886bb7026cf3b182801d4df))
* **domain:** Opportunity uses tz-aware datetime for lifecycle fields ([98e6d3b](https://github.com/yo61/jobhound/commit/98e6d3b2a09977c7f33046155c593e68e3f57f0d))
* **domain:** treat naive midnight as noon-local for bare-date hints ([69a2078](https://github.com/yo61/jobhound/commit/69a2078f1c4f1a9f6916a7b43d0baeba082f1e27))
* **infrastructure:** reject naive datetimes in meta.toml lifecycle fields ([41f0619](https://github.com/yo61/jobhound/commit/41f061932953127ebc16fcaf0a94b8af4dd3df34))
* jh file open + open_file MCP tool ([6e4507c](https://github.com/yo61/jobhound/commit/6e4507ca10fa4e6fb3cce4ba4c8eae03fc9cb111))
* **scripts:** add UTC datetime migration for existing meta.toml files ([a440998](https://github.com/yo61/jobhound/commit/a44099856e96a2eeb2dc20a16497c2cb953054c3))


### Documentation

* add CLI/MCP command naming review charter ([4107bb1](https://github.com/yo61/jobhound/commit/4107bb1b4b50fedc2b6417c27369e29269344507))
* add jh file open design spec ([a85aa00](https://github.com/yo61/jobhound/commit/a85aa001294f96f42c721e1954674deb5920ed2c))
* add shell completion design spec ([9e9ccd9](https://github.com/yo61/jobhound/commit/9e9ccd9d0449ecc92f500d799580d934cab65369))
* add UTC timestamps migration design spec ([03795e5](https://github.com/yo61/jobhound/commit/03795e5e8382e0c79ffea5bac64aae96f9cb66a4))
* **plans:** add UTC timestamps implementation plan ([4c48fe2](https://github.com/yo61/jobhound/commit/4c48fe27fdcf3c1dad0f79bf50835eb7f7cd08b1))
* **plans:** restructure to fixtures-first TDD sequence ([6d37609](https://github.com/yo61/jobhound/commit/6d376097afd74dddd79c23e28814a8831b1ce880))
* **specs:** command rename plan (locked decisions for v0.8.0) ([22f15cf](https://github.com/yo61/jobhound/commit/22f15cf2d5b20c8587dfcde43dd848a47ba5fc54))

## [0.6.1](https://github.com/yo61/jobhound/compare/v0.6.0...v0.6.1) (2026-05-14)


### Documentation

* document jh file commands + MCP file tools (37 tools) ([d7412ba](https://github.com/yo61/jobhound/commit/d7412ba641f1158943dbbb375cd22ad2442912f4))

## [0.6.0](https://github.com/yo61/jobhound/compare/v0.5.1...v0.6.0) (2026-05-14)


### Features

* **application:** file_service.append — additive write, no conflicts ([fd6c75c](https://github.com/yo61/jobhound/commit/fd6c75c13ca76a932f47fff365dad7625a4d8d82))
* **application:** file_service.delete — three-case decision ([0e8fed4](https://github.com/yo61/jobhound/commit/0e8fed447b7da75eb6003a869776d77fcfd88752))
* **application:** file_service.export — server copies to AI-provided path ([4c77eaf](https://github.com/yo61/jobhound/commit/4c77eafe80899d7c9ffd6bdf78e6cc30afa0d400))
* **application:** file_service.import_ — path-based write ([0f5af71](https://github.com/yo61/jobhound/commit/0f5af71b0c9154da43d99bc9c25388131d4dd4f3))
* **application:** file_service.write — 6-case state machine + 3-way merge ([d8c13f6](https://github.com/yo61/jobhound/commit/d8c13f69dd19a5991089ca479799a67dcb0ddbef))
* **application:** scaffold file_service with read/list/validation ([51ee2dd](https://github.com/yo61/jobhound/commit/51ee2dd42dfc8cdc5b4fb4670c6484a48998a423))
* **cli:** add jh file subcommand group (list/show/write/append/delete) ([ae4c8cd](https://github.com/yo61/jobhound/commit/ae4c8cd86d0d62860fc5e1771036982687bfb69c))
* **mcp:** add file tools (write/import/export/append/delete); move list/read ([d5500bc](https://github.com/yo61/jobhound/commit/d5500bc14eedfce54eac1ea424f97d5182bb12f2))
* **mcp:** map file_service exceptions to MCP error codes ([b893cef](https://github.com/yo61/jobhound/commit/b893cefa87dd27ee40fb22b48b9b35ebf3883b98))
* **storage:** add GitLocalFileStore — git-backed FileStore adapter ([b5a5c98](https://github.com/yo61/jobhound/commit/b5a5c98429c2847ab4e40849dafa3c2d410d281a))
* **storage:** add Revision NewType + FileStore Protocol + InMemoryFileStore ([70aa9cf](https://github.com/yo61/jobhound/commit/70aa9cfb2e5ea3b9f7029d0ca415fcbb1a4ccaa1))


### Bug Fixes

* **application:** _validate_filename rejects absolute paths + correct parent-traversal message ([517ef93](https://github.com/yo61/jobhound/commit/517ef9330a3dc1e18483b717800dc63f5308ad44))
* **application:** file_service.write — merged commit message + explicit base-recovery errors ([44fe620](https://github.com/yo61/jobhound/commit/44fe6203e653fbf003aa696d462c2c8d04a4d5ac))


### Documentation

* plan file management API implementation ([a451d6e](https://github.com/yo61/jobhound/commit/a451d6e2d336cabdff8a019bae9e1e57a24500ce))
* spec — add CLI subcommand group as peer adapter ([b30bd06](https://github.com/yo61/jobhound/commit/b30bd060598722183e88dbac16f35300023ab388))
* spec file management API + FileStore port ([cf0d217](https://github.com/yo61/jobhound/commit/cf0d21720720fa81efe2b4c43d4f101a69804129))

## [0.5.1](https://github.com/yo61/jobhound/compare/v0.5.0...v0.5.1) (2026-05-14)


### Documentation

* plan phase 4 cleanup — CLI commands -&gt; application services ([2e30c9d](https://github.com/yo61/jobhound/commit/2e30c9dd00f2d1ea9354cf0648f8010d365e5443))

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

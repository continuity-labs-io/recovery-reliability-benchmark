Task: licensing and terms documents. No source changes; tests only.

1. Code license. pyproject already has license = "Apache-2.0" and LICENSE is the Apache-2.0 text; change nothing. Add tests/test_terms.py::test_code_license_agrees asserting pyproject.toml contains 'license = "Apache-2.0"' and LICENSE contains "Apache License" and "Version 2.0".

2. DATA_LICENSE: the CC0 1.0 Universal legal code, verbatim, from https://creativecommons.org/publicdomain/zero/1.0/legalcode. If you cannot fetch it, stop and ask for it to be pasted. Do not paraphrase a license.

3. CONTRIBUTING.md
 a. Insert "## 5. Data license and use" before the current §5 "Data handling" and renumber what follows (Data handling 6, Publication 7, Withdrawal 8, Starting 9); fix any cross-references. Text:
    Contributed datasets are released under CC0 1.0 Universal; see DATA_LICENSE. Contributions are accepted only under CC0. Datasets offered under any other terms, including non-commercial or no-derivatives conditions, are not accepted. By contributing, you confirm that you hold the rights needed to deposit the data and that the data were collected under the ethics approvals applicable to your institution. Citation of the dataset and of the benchmark is requested as a norm; it is not a condition of the license. The data may be used by anyone for any purpose, including training models and building commercial products. Continuity Labs' own position as maintainer is stated in docs/terms.md.
 b. Rewrite "Data handling" (now §6): you send the dataset for analysis; the report is delivered within two weeks; the dataset is deposited in the public archive under CC0 when you confirm after reading the report. Until deposit the data are held for analysis only, shared with no third party, and deleted on request. Only deposited datasets are part of the benchmark and the publication. Delete the sentences "You decide whether your underlying data is deposited publicly.", "Public deposit is encouraged and is not required." and "A dataset that stays private contributes its derived statistics to the benchmark and nothing else."
 c. §2: change "whether or not your dataset ends up in the publication, and whether or not you choose to continue" to "whether or not you then choose to deposit".
 d. §4: add: The public archive entry carries the attribution you choose, your laboratory's name or an anonymized identifier; the paper's results table uses anonymized identifiers either way.
 e. Withdrawal (now §8): you may withdraw at any point before deposit, for any reason; the data are deleted and you keep the report. After deposit, CC0 is irrevocable: the record can be delisted from the archive and your authorship removed before journal submission, but copies already made under CC0 remain licensed. Keep the thirty-day review sentence.

4. docs/terms.md, title "# Terms", four short paragraphs with bold lead phrases, in this order:
   **Maintainer.** Continuity Labs maintains this benchmark and the data archive as a public resource, and intends to build commercial products and models on the public data and on data it generates privately.
   **No special rights.** The public data carry no rights for Continuity Labs that any other user does not have.
   **Paid engagements.** Paid engagements with Continuity Labs include a derived-data clause: Continuity Labs retains the right to use derived measures, reliability statistics, protocol metadata, and models trained on them. Raw recordings and customer identity remain confidential unless agreed otherwise. Customers may deposit raw recordings in the public archive after an embargo period in exchange for a reduced fee.
   **Governance.** Continuity Labs currently maintains the archive and intends to move governance of the data archive to a neutral body as the contributor base grows. The trigger and the form of that transfer will be set in a later version of this document.
   Footer: "This document is licensed under CC BY 4.0; see [LICENSE-DOCS](LICENSE-DOCS)." (relative link from docs/ is ../LICENSE-DOCS).

5. README.md "Licensing": add "Contributed datasets are released under CC0 1.0; see DATA_LICENSE and CONTRIBUTING.md §5. Continuity Labs' position as maintainer is in docs/terms.md." Add docs/terms.md to the CC BY 4.0 list.

6. CHANGELOG.md (create; Keep a Changelog format; "## Unreleased"): "Data license: contributed datasets are accepted under CC0 1.0 only (DATA_LICENSE, CONTRIBUTING.md §5); report-then-deposit sequence and withdrawal terms updated to match." and "docs/terms.md: maintainer position, paid-engagement derived-data clause, governance intent."

7. tests/test_terms.py: test_code_license_agrees; test_data_license_present ("CC0 1.0 Universal" in DATA_LICENSE); test_contributing_data_section ("## 5. Data license and use" present, "CC0" and "DATA_LICENSE" in that section, the three deleted sentences absent); test_terms_doc (README contains "docs/terms.md"; the file exists and contains the four bold lead phrases); test_changelog_mentions_cc0.

Run the full suite and make it pass.

# Changelog

## v0.21.4 beta

### Added
- **Keep existing translations** (Settings → Translation Quality): incremental runs. If a `texts_*.xml` for a target language already exists in the output folder, every source text whose `<GUID>` or `<LineId>` is already present there is skipped and the stored translation is kept.

  ```xml
  <!-- identifier before the text -->
  <Text>
    <GUID>1010364</GUID>
    <Text>Beer</Text>
  </Text>

  <!-- identifier after the text -->
  <Text>
    <Text>Beer</Text>
    <LineId>2144000000</LineId>
  </Text>
  ```

  - The identifier may appear before or after the inner `<Text>` element.
  - `<GUID>` and `<LineId>` are matched case-insensitively, so `<Guid>` and `<LineID>` work as well.
  - Text blocks without an identifier cannot be matched and are always translated.
  - Only texts that are still missing are sent to the language models; progress, ETA and text counters reflect the reduced workload in both Sequential and Parallel mode.
  - A missing or unreadable target file is reported as a warning and simply treated as "nothing to reuse"; the run is never aborted.
  - The setting is persisted in `config.ini` as `keep_existing_translations` and is disabled by default.

## v0.20.2 beta

### Added
- `<!-- DONOTTRANSLATE -->` comment marker: the following element and its subtree are copied 1:1 instead of being translated.

  ```xml
  <ModOp Add="/TextExport/Texts">
    <Text>
      <!--!DONOTTRANSLATE-->
      <Text>_____Test001_____</Text>
      <LineId>2144000003</LineId>
    </Text>
  </ModOp>

### Fixed
- Underscore handling: underscore runs are now preserved exactly, and underscore texts no longer get invented punctuation (`_____Test001_____` returned as `_____Teste001._____`).
# Changelog

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
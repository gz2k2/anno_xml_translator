# Anno XML Translator

[English](#english) | [Deutsch](#deutsch)

---

# English

## Anno XML Translator

A local desktop tool for automatically translating Anno XML language files with **Argos Translate**. The application reads translatable `<Text>` elements from an XML file, creates separate output files for the selected target languages, and provides language profiles, fixed exclusions, protected proper names, defined name translations, and a translation memory.

## Features

- Local translation with Argos Translate
- Processing of XML files containing `<Text>` elements
- Output for multiple target languages
- Sequential or parallel translation mode
- Automatic download of required Argos language models
- Language profiles for frequently used target-language selections
- Fixed exclusions with `*` wildcard support
- `<!--!DONOTRANSLATE-->` comment marker to exclude single texts or whole blocks directly in the XML
- Protection of proper names that must remain unchanged
- Defined translations for names in individual languages
- Translation memory for recurring texts
- Protection of square-bracket content and XML/HTML tags
- Configurable default output folder
- Progress, runtime, ETA, preview, and logging

## Requirements

A current Python 3 installation and a dedicated virtual environment are recommended.

Install the required Python packages:

```bash
pip install customtkinter requests argostranslate
```

Depending on the installed Argos Translate version and its sentence-segmentation configuration, additional dependencies may be installed automatically.

## Starting the application

```bash
python Anno_XML_Translator.py
```

On first start, the application creates the `config`, `argos_packages`, and `temp` folders next to the Python script or compiled executable.

## Quick start

1. Start the application.
2. Open the **Language Selection** tab.
3. Select the required target languages.
4. Return to the **Main Menu** tab.
5. Select the source XML file with **Browse**.
6. Check the output folder.
7. Click **Start Translation**.
8. Monitor progress and messages in the log.
9. The translated XML files are written to the selected output folder.

## Main Menu

### Source File

Use **Browse** to select the XML file that should be translated. The tool processes non-empty `<Text>` elements that do not contain child elements.

Example:

```xml
<Text>Der Kronenhafen benötigt mehr Arbeiter.</Text>
```

### Output Folder

This field shows the output folder for the current run. Use **Select Folder** to override it for this run.

The output folder is determined in this order:

1. Folder selected manually in the Main Menu
2. Default output folder configured in **Settings**
3. Folder containing the source file

### Progress and preview

During translation, the Main Menu displays:

- Number of processed texts
- Current status
- Elapsed runtime
- Estimated remaining time
- Most recently submitted source text
- Most recently received translation
- Technical messages in the log

### Start Translation / Cancel Translation

**Start Translation** begins processing. During an active run, the button changes to **Cancel Translation**. Cancellation is requested in a controlled manner and may take effect after the current processing step has completed.

## Language Selection and profiles

The **Language Selection** tab defines the target languages.

### Select All and Deselect All

- **Select All** enables all available target languages.
- **Deselect All** clears the complete selection.

The detected source language is not processed again as a target language.

### Language Profile

Language profiles save frequently used target-language combinations.

- **Save Profile** saves the current language selection under a profile name.
- **Delete Profile** removes the selected profile.
- The **Language Profile** dropdown loads a saved selection.

Profiles are stored in:

```text
language_profiles.json
```

## Settings

### Translation Mode

Defines how multiple target languages are processed.

#### Sequential

Target languages are translated one after another.

Recommended for:

- Systems with limited memory
- CPU processing
- Stable and easily traceable processing

#### Parallel

Multiple target languages are translated concurrently using background threads.

Recommended for:

- More powerful systems
- Several target languages
- Shorter overall processing time

Parallel processing can substantially increase memory usage because several translation models may be loaded at the same time.

### Batch Size (Texts)

Defines how many XML texts are grouped into one processing step.

- Smaller values use less memory.
- Larger values can improve processing speed.
- Very large values are not recommended for long texts or systems with limited memory.

Batch size does not automatically improve linguistic translation quality.

### Auto-Batching (by characters)

When enabled, the tool additionally limits each batch by its total number of characters.

- **Enable** activates automatic character-based limiting.
- **Max Characters** defines the maximum number of characters per batch.

This is useful when an XML file contains a mixture of very short and very long texts.

### Processing Mode

Controls the internal CTranslate2 compute type.

#### GPU - Fast and efficient (float16)

- Intended for compatible GPUs
- Uses less graphics memory than `float32`
- Usually the appropriate selection for GPU operation

#### CPU - Fast, low memory usage (int8)

- Recommended for CPU operation
- Reduced system-memory usage
- Suitable default for computers without a compatible GPU

#### Maximum compatibility (float32)

- Highest numerical precision
- Increased memory demand
- Useful as a compatibility or diagnostic mode

This option mainly affects speed, memory consumption, and hardware compatibility. Translation models, direct language routes, protected terminology, and translation memory have a greater impact on linguistic quality.

### Default Output Folder

Defines a persistent default output folder.

- **Select Folder** selects and saves the folder.
- **Clear** removes the configured default.
- If the field is empty, the source file folder is used.

The setting is stored in `config.ini`:

```ini
[Settings]
default_output_directory = C:\Anno\Translations\Output
```

The output folder can still be overridden in the Main Menu for an individual run.

## Translation Settings

The **Translation Settings** tab manages text exclusions, multilingual name definitions, and protected proper names.

### Fixed Exclusions

Fixed exclusions prevent an **entire XML text** from being translated. Matching is case-insensitive. Placed at the top of the **Translation Settings** tab.

Separate multiple patterns with commas:

```text
test_text*, test_test*, quest_*, research_*
```

The `*` character matches any following characters.

For example, this pattern:

```text
test_text*
```

completely excludes:

```text
Test_Text
test_TEXT
test_text_hello
test_text1234
```

A pattern without `*` only matches the complete text:

```text
Custom Text
```

As soon as a fixed exclusion matches, the complete original text is retained. It is not sent to Argos Translate and no part of it is translated.

### DONOTTRANSLATE marker

Fixed exclusions are configured in the application. The `<!--!DONOTTRANSLATE-->` marker works the other way round: it is written **directly into the XML file**, so the exclusion travels with the mod source and needs no configuration at all.

The marker is an XML comment placed in front of the element that must not be translated. The following element and everything inside it are copied into every output file unchanged:

```xml
<ModOp Add="/TextExport/Texts">
  <Text>
    <!--!DONOTTRANSLATE-->
    <Text>_____Test001_____</Text>
    <LineId>2144000003</LineId>
  </Text>
</ModOp>
```

In this example, `_____Test001_____` is written to every language file exactly as it appears in the source.

**Scope**

The marker applies to the next element only, including all of its child elements. It can therefore protect a single text or a complete block:

```xml
<!--!DONOTTRANSLATE-->
<ModOp Add="/TextExport/Texts">
  <Text>
    <Text>_____Section_Header_____</Text>
    <LineId>2144000010</LineId>
  </Text>
  <Text>
    <Text>_____Section_Footer_____</Text>
    <LineId>2144000011</LineId>
  </Text>
</ModOp>
```

**Accepted spellings**

Matching ignores capitalization, whitespace, a leading `!`, underscores, and hyphens. All of the following are recognized as the same instruction:

```xml
<!--!DONOTTRANSLATE-->
<!-- DONOTTRANSLATE -->
<!-- DoNotTranslate -->
<!--!DO_NOT_TRANSLATE-->
```

**Behavior**

- Protected texts are never sent to Argos Translate.
- Protected texts are not written to the translation memory.
- Proper names, name translations, and fixed exclusions are not evaluated for them, because no translation takes place.
- The number of protected texts is reported once per run in the log.

Use this marker for technical identifiers, separators, placeholder rows, and any text whose exact spelling is required by the game.

### Name Translations (name_translations.ini)

The **Translation Settings** tab provides an interactive combobox and entry form for `name_translations.ini`:

- **Select Entry**: Dropdown menu listing all entry identifiers.
- **Input Form**: Edit entry identifier and translations per language (`de`, `en`, `fr`, `es`, `it`, `pl`, etc.).
- **Actions**: **New Entry**, **Save Entry**, and **Delete Entry** buttons update `name_translations.ini` in real time.

Default terms defined in `anno_translator/default_translation_data.py` (such as Anno population tiers `Plebeians`, `Equites`, `Patricians`, `Liberti`, `Waders`, `Smiths`, `Aldermen`, `Mercators`, `Nobles`) are **always active** and merged with user entries in `name_translations.ini`.

### Protected Proper Names (proper_names.ini)

Manages names that must remain unchanged across all languages:

- **Select Name**: Dropdown menu listing all proper names.
- **Input Form**: Entry field for the proper name string.
- **Actions**: **New Entry**, **Save Name**, and **Delete Selected** buttons update `proper_names.ini`.

Built-in proper names in `default_translation_data.py` are continuously merged with `proper_names.ini`.

## Translation Quality

### Protect proper names from proper_names.ini

Protects names that must remain unchanged in every language.

Example `proper_names.ini`:

```ini
[ProperNames]
name_001 = Anno
name_002 = Crown Falls

[Settings]
case_sensitive = false
```

With `case_sensitive = false`, a name is detected regardless of capitalization. The spelling stored in the INI file is used when the name is restored.

Example:

```text
Build a warehouse in Crown Falls.
```

`Crown Falls` remains unchanged while the rest of the sentence is translated.

### Use defined name translations from name_translations.ini

Enables predefined language-specific translations for names and special terms.

Example:

```ini
[Settings]
case_sensitive = false

[Test_Entry]
de = Testeintrag
en = Test Entry
fr = Entrée de test
es = Entrada de prueba
it = Voce di prova
pl = Wpis testowy

```

A section name such as `[Test_Entry]` is only a unique internal identifier. The source and target spellings are defined by the language-code entries.

For an English-to-German translation, `Test Entry` is protected before machine translation and then restored as `Testeintrag`.

If no value exists for the requested target language, the source-language spelling remains unchanged.

### Use Translation Memory

Reuses previously stored complete translations.

Before running Argos Translate, the tool checks:

1. Language route
2. Complete source text
3. Existing target text

An exact match is returned directly. This keeps recurring text consistent and avoids unnecessary processing.

The entries are stored in:

```text
translation_memory.ini
```

Example:

```ini
[TM_de_to_en_1234567890abcdef]
route = de_to_en
source = Baue ein neues Lagerhaus.
target = Build a new warehouse.
```

### Automatically store new translations

When enabled, newly generated translations are automatically added to the translation memory.

Recommendation:

- Enable it for automatic consistency across recurring texts.
- Disable it if only manually reviewed translations should be stored permanently.

Existing memory entries can still be used when **Use Translation Memory** is enabled, even if automatic storage is disabled.

### Quality-file buttons

#### Reload INI Files

Reloads these files without restarting the application:

- `proper_names.ini`
- `name_translations.ini`
- `translation_memory.ini`

Use this after manually editing and saving one of the files.

#### Open Proper Names

Opens `proper_names.ini` in the operating system's default editor.

#### Open Name Translations

Opens `name_translations.ini` in the default editor.

#### Open Memory

Opens `translation_memory.ini` in the default editor.

## Processing order

Each text is processed in this order:

1. Skip texts marked with `<!--!DONOTRANSLATE-->` and copy them unchanged
2. Check fixed exclusions
3. Retain the complete original text on an exclusion match
4. Search for an exact translation-memory match
5. Protect language-specific names from `name_translations.ini`
6. Protect unchanged names from `proper_names.ini`
7. Protect square-bracket content and XML/HTML tags
8. Translate the remaining text with Argos Translate
9. Restore unchanged proper names
10. Insert language-specific name translations
11. Optionally store the result in translation memory

## Automatically created files and folders

### config.ini

Stores general application settings, including:

- Translation mode
- Batch size
- Auto-batching
- Processing mode
- Default output folder
- Fixed exclusions
- Enabled quality options
- Selected language profile

### language_profiles.json

Contains saved target-language profiles.

### proper_names.ini

Contains proper names that must remain unchanged in every language.

### name_translations.ini

Contains defined name translations by language code.

### translation_memory.ini

Contains stored complete translations grouped by language route.

### argos_packages

Contains locally installed Argos language models.

### temp

Contains local cache data and language resources used by the application.

## Recommendations for translation quality

1. Use direct language models whenever available.
2. Maintain recurring special terms in `name_translations.ini`.
3. Add unchanged brand and proper names to `proper_names.ini`.
4. Use translation memory for recurring and reviewed texts.
5. Use fixed exclusions only for complete custom texts that must never be translated.
6. Manually review short and ambiguous texts.
7. Back up the INI files regularly, especially after manual corrections.

## Troubleshooting

### No language model is available

Check the internet connection during the first download of a model. Installed models can subsequently be used locally.

### GPU mode does not work

Select:

```text
CPU - Fast, low memory usage (int8)
```

Not every Python, CUDA, or CTranslate2 installation supports `float16` on the available hardware.

### The output folder is incorrect

1. Check the output path in the Main Menu.
2. Check **Default Output Folder** in **Settings**.
3. Use **Clear** to return to the source-file-folder behavior.

### INI file changes are not applied

After saving the files, click:

```text
Reload INI Files
```

### A text is translated despite a fixed exclusion

Check whether the pattern matches the complete text.

```text
test_text*
```

matches `Test_Text_123`, but not `My_Test_Text_123`, because the latter does not begin with `test_text`.

### A DONOTRANSLATE marker has no effect

Check the following:

- Is the comment placed **in front of** the element and inside the same parent element?
- Does the comment contain only the marker, without additional text?
- Is the text really inside the protected element? The marker covers the next element only.
- Was the source file saved before the run was started?

### A name is not replaced

Check the following:

- Is the corresponding option enabled?
- Is the language code correct?
- Were the INI files reloaded?
- Is a source value defined for the detected source language?
- Does the XML file contain the expected spelling?

## Backup

Before larger translation runs, back up:

```text
config.ini
language_profiles.json
proper_names.ini
name_translations.ini
translation_memory.ini
```

The original XML file should also be retained unchanged.

## License and disclaimer

The tool modifies XML content automatically. Translations should be reviewed for technical and linguistic correctness before publication. Version control or regular backups of source and output files are recommended for production mod projects.

---

# Deutsch

## Anno XML Translator

Ein lokales Desktop-Werkzeug zur automatischen Übersetzung von Anno-XML-Sprachdateien mit **Argos Translate**. Das Tool liest übersetzbare `<Text>`-Elemente aus einer XML-Datei, erzeugt für die ausgewählten Zielsprachen separate Ausgabedateien und bietet Funktionen für Sprachprofile, feste Ausschlüsse, Eigennamen, definierte Namensübersetzungen und ein Translation Memory.

## Funktionsumfang

- Lokale Übersetzung mit Argos Translate
- Verarbeitung von XML-Dateien mit `<Text>`-Elementen
- Gleichzeitige Ausgabe für mehrere Zielsprachen
- Sequentieller oder paralleler Übersetzungsmodus
- Automatischer Download benötigter Argos-Sprachmodelle
- Sprachprofile für häufig genutzte Zielsprachen
- Feste Ausschlüsse mit `*`-Wildcard
- Kommentar-Marker `<!--!DONOTRANSLATE-->` zum Ausschluss einzelner Texte oder ganzer Blöcke direkt in der XML-Datei
- Schutz unveränderlicher Eigennamen
- Definierte Übersetzungen für Eigennamen je Sprache
- Translation Memory für wiederkehrende Texte
- Schutz von Bereichen in eckigen Klammern und XML-/HTML-Tags
- Einstellbarer Standard-Ausgabeordner
- Fortschrittsanzeige, Laufzeit, Restzeitschätzung und Protokoll

## Voraussetzungen

Empfohlen wird eine aktuelle Python-3-Version mit einer eigenen virtuellen Umgebung.

Benötigte Python-Pakete:

```bash
pip install customtkinter requests argostranslate
```

Abhängig von der verwendeten Argos-Version und Satzsegmentierung können zusätzliche Pakete automatisch als Abhängigkeiten installiert werden.

## Programm starten

```bash
python Anno_XML_Translator.py
```

Beim ersten Start legt das Tool die Ordner `config`, `argos_packages` und `temp` neben dem Python-Skript beziehungsweise der kompilierten EXE an.

## Schnellstart

1. Starte das Programm.
2. Öffne den Tab **Language Selection**.
3. Wähle die gewünschten Zielsprachen aus.
4. Öffne den Tab **Main Menu**.
5. Wähle über **Browse** die Quell-XML-Datei aus.
6. Prüfe den Ausgabeordner.
7. Klicke auf **Start Translation**.
8. Verfolge Fortschritt und Meldungen im Protokoll.
9. Die übersetzten XML-Dateien werden im gewählten Ausgabeordner gespeichert.

## Hauptmenü

### Source File

Über **Browse** wird die zu übersetzende XML-Datei ausgewählt. Das Tool verarbeitet nichtleere `<Text>`-Elemente ohne untergeordnete XML-Elemente.

Beispiel:

```xml
<Text>Der Kronenhafen benötigt mehr Arbeiter.</Text>
```

### Output Folder

Hier wird der Ausgabeordner für den aktuellen Übersetzungslauf angezeigt. Über **Select Folder** kann er für diesen Lauf geändert werden.

Die Reihenfolge für die Ermittlung des Ausgabeordners lautet:

1. Manuell im Hauptmenü gewählter Ausgabeordner
2. Unter **Settings** definierter Standard-Ausgabeordner
3. Ordner der ausgewählten Quelldatei

### Fortschritt und Vorschau

Während der Übersetzung zeigt das Hauptmenü:

- Anzahl verarbeiteter Texte
- aktuellen Status
- bisherige Laufzeit
- geschätzte Restzeit
- zuletzt gesendeten Ausgangstext
- zuletzt empfangene Übersetzung
- technische Meldungen im Log

### Start Translation / Cancel Translation

Mit **Start Translation** beginnt die Verarbeitung. Während eines aktiven Laufs ändert sich die Schaltfläche zu **Cancel Translation**. Ein Abbruch wird kontrolliert angefordert und kann nach dem aktuell laufenden Verarbeitungsschritt wirksam werden.

## Sprachauswahl und Profile

Im Tab **Language Selection** werden die Zielsprachen festgelegt.

### Select All und Deselect All

- **Select All** aktiviert alle angebotenen Zielsprachen.
- **Deselect All** entfernt die gesamte Auswahl.

Die erkannte Ausgangssprache wird nicht erneut als Zielsprache verarbeitet.

### Language Profile

Sprachprofile speichern häufig verwendete Kombinationen von Zielsprachen.

- **Save Profile** speichert die aktuelle Auswahl unter einem Profilnamen.
- **Delete Profile** löscht das ausgewählte Profil.
- Das Dropdown **Language Profile** lädt eine gespeicherte Auswahl.

Die Profile werden in folgender Datei gespeichert:

```text
language_profiles.json
```

## Einstellungen

### Translation Mode

Legt fest, wie mehrere Zielsprachen verarbeitet werden.

#### Sequential

Die Zielsprachen werden nacheinander übersetzt.

Geeignet für:

- Systeme mit wenig Arbeitsspeicher
- CPU-Verarbeitung
- möglichst stabile und leicht nachvollziehbare Verarbeitung

#### Parallel

Mehrere Zielsprachen werden gleichzeitig über Hintergrund-Threads verarbeitet.

Geeignet für:

- leistungsfähigere Systeme
- mehrere Zielsprachen
- kürzere Gesamtlaufzeit

Parallelbetrieb kann den Speicherbedarf deutlich erhöhen, da mehrere Übersetzungsmodelle gleichzeitig geladen werden können.

### Batch Size (Texts)

Bestimmt, wie viele XML-Texte in einem Verarbeitungsschritt zusammengefasst werden.

- Kleine Werte benötigen weniger Speicher.
- Größere Werte können die Verarbeitung beschleunigen.
- Sehr große Werte sind bei langen Texten oder wenig Arbeitsspeicher nicht empfehlenswert.

Die Batchgröße verbessert nicht automatisch die sprachliche Übersetzungsqualität.

### Auto-Batching (by characters)

Bei aktivierter Option begrenzt das Tool einen Batch zusätzlich anhand der gesamten Zeichenzahl.

- **Enable** aktiviert die automatische Begrenzung.
- **Max Characters** definiert die maximale Zeichenzahl pro Batch.

Diese Einstellung ist sinnvoll, wenn die XML-Datei sowohl sehr kurze als auch sehr lange Texte enthält. Dadurch werden übermäßig große Batches vermieden.

### Processing Mode

Das Dropdown steuert den internen CTranslate2-Rechentyp.

#### GPU - Fast and efficient (float16)

- Für kompatible GPUs vorgesehen
- Geringerer Grafikspeicherbedarf als `float32`
- In der Regel die passende Auswahl für GPU-Betrieb

#### CPU - Fast, low memory usage (int8)

- Für CPU-Betrieb empfohlen
- Geringerer Arbeitsspeicherbedarf
- Gute Standardauswahl für Rechner ohne kompatible GPU

#### Maximum compatibility (float32)

- Höchste numerische Genauigkeit
- Höherer Speicherbedarf
- Sinnvoll als Kompatibilitäts- oder Diagnosemodus

Die Auswahl beeinflusst hauptsächlich Geschwindigkeit, Speicherbedarf und Hardwarekompatibilität. Der größte Einfluss auf die sprachliche Qualität entsteht durch das verwendete Sprachmodell, direkte Übersetzungsrouten, Eigennamen und das Translation Memory.

### Default Output Folder

Definiert einen dauerhaft verwendeten Standard-Ausgabeordner.

- **Select Folder** wählt und speichert den Ordner.
- **Clear** entfernt den Standardwert.
- Bei leerem Feld wird der Ordner der Quelldatei verwendet.

Die Einstellung wird in `config.ini` gespeichert:

```ini
[Settings]
default_output_directory = C:\Anno\Translations\Output
```

Der Ausgabeordner im Hauptmenü kann weiterhin für einzelne Läufe überschrieben werden.

## Translation Settings

Der Tab **Translation Settings** verwaltet Feste Ausschlüsse, mehrsprachige Namensübersetzungen und geschützte Eigennamen.

### Fixed Exclusions

Feste Ausschlüsse verhindern die Übersetzung eines **vollständigen XML-Textes**. Die Prüfung erfolgt ohne Beachtung der Groß- und Kleinschreibung. Befindet sich ganz oben im Tab **Translation Settings**.

Mehrere Muster werden durch Kommas getrennt:

```text
test_text*, test_test*, quest_*, research_*
```

Ein `*` steht für beliebige nachfolgende Zeichen.

Das Muster:

```text
test_text*
```

schließt beispielsweise vollständig aus:

```text
Test_Text
test_TEXT
test_text_hallo
test_text1234
```

Ein Muster ohne `*` trifft nur auf den vollständigen Text zu:

```text
Custom Text
```

Sobald ein Ausschluss zutrifft, bleibt der gesamte Text unverändert. Er wird weder an Argos Translate gesendet noch in Teilen übersetzt.

### DONOTTRANSLATE-Marker

Feste Ausschlüsse werden im Programm konfiguriert. Der Marker `<!--!DONOTRANSLATE-->` funktioniert umgekehrt: Er wird **direkt in die XML-Datei** geschrieben. Der Ausschluss bleibt damit Teil der Mod-Quelldatei und erfordert keinerlei Konfiguration.

Der Marker ist ein XML-Kommentar, der vor dem Element steht, das nicht übersetzt werden soll. Das nachfolgende Element wird mit seinem gesamten Inhalt unverändert in jede Ausgabedatei übernommen:

```xml
<ModOp Add="/TextExport/Texts">
  <Text>
    <!--!DONOTRANSLATE-->
    <Text>_____Test001_____</Text>
    <LineId>2144000003</LineId>
  </Text>
</ModOp>
```

In diesem Beispiel wird `_____Test001_____` in jede Sprachdatei exakt so geschrieben, wie es in der Quelldatei steht.

**Geltungsbereich**

Der Marker gilt nur für das unmittelbar folgende Element, einschließlich aller untergeordneten Elemente. Er kann deshalb sowohl einen einzelnen Text als auch einen kompletten Block schützen:

```xml
<!--!DONOTRANSLATE-->
<ModOp Add="/TextExport/Texts">
  <Text>
    <Text>_____Section_Header_____</Text>
    <LineId>2144000010</LineId>
  </Text>
  <Text>
    <Text>_____Section_Footer_____</Text>
    <LineId>2144000011</LineId>
  </Text>
</ModOp>
```

**Zulässige Schreibweisen**

Groß- und Kleinschreibung, Leerzeichen, ein führendes `!`, Unterstriche und Bindestriche werden bei der Prüfung ignoriert. Die folgenden Varianten werden alle als dieselbe Anweisung erkannt:

```xml
<!--!DONOTRANSLATE-->
<!-- DONOTTRANSLATE -->
<!-- DoNotTranslate -->
<!--!DO_NOT_TRANSLATE-->
```

**Verhalten**

- Geschützte Texte werden nie an Argos Translate gesendet.
- Geschützte Texte werden nicht im Translation Memory gespeichert.
- Eigennamen, Namensübersetzungen und feste Ausschlüsse werden für sie nicht ausgewertet, da keine Übersetzung stattfindet.
- Die Anzahl der geschützten Texte wird einmal pro Lauf im Protokoll ausgegeben.

Der Marker eignet sich für technische Bezeichner, Trennzeilen, Platzhalter und alle Texte, deren exakte Schreibweise vom Spiel benötigt wird.

### Name Translations (name_translations.ini)

Der Tab **Translation Settings** bietet ein interaktives Dropdown-Menü und eine Eingabemaske für `name_translations.ini`:

- **Select Entry**: Dropdown-Auswahl aller Begriffs-Abschnitte.
- **Eingabemaske**: Bearbeitung von Bezeichner und Übersetzungen je Sprache (`de`, `en`, `fr`, `es`, `it`, `pl` etc.).
- **Aktionen**: **New Entry**, **Save Entry** und **Delete Entry** aktualisieren die `name_translations.ini` direkt.

Standardbegriffe aus `anno_translator/default_translation_data.py` (z. B. Anno-Bevölkerungsstufen wie `Plebeians`, `Equites`, `Patricians`, `Liberti`, `Waders`, `Smiths`, `Aldermen`, `Mercators`, `Nobles`) sind **immer aktiv** und werden automatisch mit den Benutzereinträgen in `name_translations.ini` zusammengeführt.

### Protected Proper Names (proper_names.ini)

Verwaltet Eigennamen, die in jeder Sprache unverändert bleiben müssen:

- **Select Name**: Dropdown-Auswahl aller Eigennamen.
- **Eingabemaske**: Eingabefeld für die Namens-Zeichenkette.
- **Aktionen**: **New Entry**, **Save Name** und **Delete Selected** aktualisieren `proper_names.ini`.

Integreite Eigennamen aus `default_translation_data.py` werden kontinuierlich mit `proper_names.ini` zusammengeführt.

## Translation Quality

### Protect proper names from proper_names.ini

Aktiviert den Schutz von Eigennamen, die in jeder Sprache unverändert bleiben müssen.

Beispiel für `proper_names.ini`:

```ini
[ProperNames]
name_001 = Anno
name_002 = Crown Falls

[Settings]
case_sensitive = false
```

Bei `case_sensitive = false` wird der Name unabhängig von Groß- und Kleinschreibung erkannt. Beim Wiederherstellen wird die Schreibweise aus der INI-Datei verwendet.

Beispiel:

```text
Build a warehouse in Crown Falls.
```

`Crown Falls` wird geschützt, während der restliche Satz übersetzt wird.

### Use defined name translations from name_translations.ini

Aktiviert fest definierte Übersetzungen für Eigennamen oder spezielle Begriffe. Für jeden Namen kann je Sprachcode eine gewünschte Schreibweise hinterlegt werden.

Beispiel:

```ini
[Settings]
case_sensitive = false

[Test_Entry]
de = Testeintrag
en = Test Entry
fr = Entrée de test
es = Entrada de prueba
it = Voce di prova
pl = Wpis testowy

Der Abschnittsname, beispielsweise `[Test_Entry]`, ist nur eine eindeutige interne Kennung. Die tatsächlichen Such- und Zielwerte stehen hinter den Sprachcodes.

Bei einer Übersetzung von Englisch nach Deutsch wird `Test Entry` vor der maschinellen Übersetzung geschützt und anschließend als `Testeintrag` eingesetzt.

Ist für die Zielsprache kein Wert definiert, bleibt die Bezeichnung in der Schreibweise der Ausgangssprache erhalten.

### Use Translation Memory

Aktiviert die Wiederverwendung bereits gespeicherter vollständiger Übersetzungen.

Vor einer neuen Argos-Übersetzung prüft das Tool:

1. Sprachrichtung
2. vollständigen Ausgangstext
3. vorhandenen Zieleintrag

Bei einem exakten Treffer wird die gespeicherte Übersetzung verwendet. Dadurch bleiben wiederkehrende Texte konsistent und müssen nicht erneut berechnet werden.

Die Daten werden in folgender Datei gespeichert:

```text
translation_memory.ini
```

Beispiel:

```ini
[TM_de_to_en_1234567890abcdef]
route = de_to_en
source = Baue ein neues Lagerhaus.
target = Build a new warehouse.
```

### Automatically store new translations

Wenn diese Option aktiviert ist, werden neu erzeugte Übersetzungen automatisch im Translation Memory gespeichert.

Empfehlung:

- Aktivieren, wenn wiederkehrende Texte automatisch konsistent verarbeitet werden sollen.
- Deaktivieren, wenn nur manuell geprüfte Übersetzungen dauerhaft gespeichert werden sollen.

Bereits gespeicherte Einträge können bei aktiviertem **Use Translation Memory** weiterhin verwendet werden, auch wenn das automatische Speichern deaktiviert ist.

### Schaltflächen für Qualitätsdateien

#### Reload INI Files

Lädt die folgenden Dateien neu, ohne das Programm neu zu starten:

- `proper_names.ini`
- `name_translations.ini`
- `translation_memory.ini`

Nach manuellen Änderungen an einer dieser Dateien sollte diese Funktion verwendet werden.

#### Open Proper Names

Öffnet `proper_names.ini` im Standardeditor des Betriebssystems.

#### Open Name Translations

Öffnet `name_translations.ini` im Standardeditor des Betriebssystems.

#### Open Memory

Öffnet `translation_memory.ini` im Standardeditor des Betriebssystems.

## Verarbeitungsreihenfolge

Jeder Text wird grundsätzlich in dieser Reihenfolge behandelt:

1. Überspringen der mit `<!--!DONOTRANSLATE-->` markierten Texte und unveränderte Übernahme
2. Prüfung der festen Ausschlüsse
3. Übernahme des Originals bei einem Ausschlusstreffer
4. Suche nach einem exakten Translation-Memory-Treffer
5. Schutz sprachabhängig übersetzter Namen aus `name_translations.ini`
6. Schutz unveränderlicher Namen aus `proper_names.ini`
7. Schutz vorhandener Bereiche in eckigen Klammern sowie XML-/HTML-Tags
8. Übersetzung der verbleibenden Textteile mit Argos Translate
9. Wiederherstellung unveränderlicher Namen
10. Einsetzen der sprachabhängigen Namensübersetzungen
11. Optionales Speichern im Translation Memory

## Automatisch angelegte Dateien und Ordner

### config.ini

Speichert allgemeine Programmeinstellungen, beispielsweise:

- Übersetzungsmodus
- Batchgröße
- Auto-Batching
- Processing Mode
- Standard-Ausgabeordner
- Ausschlussmuster
- aktivierte Qualitätsoptionen
- ausgewähltes Sprachprofil

### language_profiles.json

Enthält gespeicherte Zielsprachenprofile.

### proper_names.ini

Enthält Eigennamen, die in allen Sprachen unverändert bleiben sollen.

### name_translations.ini

Enthält definierte Namensübersetzungen je Sprachcode.

### translation_memory.ini

Enthält bereits gespeicherte vollständige Übersetzungen je Sprachrichtung.

### argos_packages

Enthält lokal installierte Argos-Sprachmodelle.

### temp

Wird unter anderem für lokale Cache- und Sprachressourcen verwendet.

## Empfehlungen für gute Übersetzungsqualität

1. Verwende direkte Sprachmodelle, sofern verfügbar.
2. Pflege wiederkehrende Spezialbegriffe in `name_translations.ini`.
3. Trage unveränderliche Marken- und Eigennamen in `proper_names.ini` ein.
4. Nutze das Translation Memory für wiederkehrende und geprüfte Texte.
5. Verwende feste Ausschlüsse nur für vollständige Custom-Texte, die überhaupt nicht übersetzt werden dürfen.
6. Prüfe besonders kurze und mehrdeutige Texte manuell.
7. Sichere die INI-Dateien regelmäßig, insbesondere nach manuellen Korrekturen.

## Fehlerbehebung

### Kein Sprachmodell verfügbar

Prüfe die Internetverbindung beim erstmaligen Herunterladen eines Modells. Bereits installierte Modelle können anschließend lokal verwendet werden.

### GPU-Modus funktioniert nicht

Wähle unter **Processing Mode**:

```text
CPU - Fast, low memory usage (int8)
```

Nicht jede Python-, CUDA- oder CTranslate2-Installation unterstützt `float16` auf der vorhandenen Hardware.

### Ausgabeordner ist falsch

1. Prüfe den Pfad im Hauptmenü.
2. Prüfe **Default Output Folder** unter **Settings**.
3. Verwende **Clear**, wenn wieder der Ordner der Quelldatei verwendet werden soll.

### Änderungen an INI-Dateien werden nicht verwendet

Klicke nach dem Speichern auf:

```text
Reload INI Files
```

### Ein Text wird trotz Ausschluss übersetzt

Prüfe, ob das Muster auf den vollständigen Text passt.

Beispiel:

```text
test_text*
```

trifft auf `Test_Text_123` zu, aber nicht auf `Mein_Test_Text_123`, da der Text nicht mit `test_text` beginnt.

### Der DONOTTRANSLATE-Marker wirkt nicht

Prüfe:

- Steht der Kommentar **vor** dem Element und innerhalb desselben übergeordneten Elements?
- Enthält der Kommentar ausschließlich den Marker ohne zusätzlichen Text?
- Liegt der Text tatsächlich innerhalb des geschützten Elements? Der Marker gilt nur für das unmittelbar folgende Element.
- Wurde die Quelldatei vor dem Start des Laufs gespeichert?

### Ein Name wird nicht ersetzt

Prüfe:

- Ist die zugehörige Checkbox aktiviert?
- Ist der Sprachcode korrekt?
- Wurde die INI-Datei neu geladen?
- Ist der Ausgangsname für die erkannte Quellsprache vorhanden?
- Enthält die XML-Datei exakt den erwarteten Namen?

## Datensicherung

Vor größeren Übersetzungsläufen empfiehlt sich eine Sicherung dieser Dateien:

```text
config.ini
language_profiles.json
proper_names.ini
name_translations.ini
translation_memory.ini
```

Die ursprüngliche XML-Datei sollte ebenfalls unverändert aufbewahrt werden.

## Lizenz und Haftung

Das Tool verändert XML-Inhalte automatisiert. Übersetzungen sollten vor einer Veröffentlichung fachlich und sprachlich geprüft werden. Für produktive Mod-Projekte empfiehlt sich außerdem eine Versionsverwaltung oder regelmäßige Sicherung der Ausgangs- und Zieldateien.

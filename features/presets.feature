# language: en
Feature: Dither presets
  As a beatmaker
  I want to save and reuse my dither settings
  To keep a consistent visual style

  Scenario: Preset roundtrip saves and reloads
    Given a temporary presets directory
    When I save the "GherkinTest" preset with floyd method and VAPOR palette
    Then I reload "GherkinTest" with the same values

  Scenario: Bundled presets never overwrite edits
    Given a temporary presets directory with bundled presets
    When I hand-edit SLIME_FS and re-ensure bundled presets
    Then my edit is preserved

# language: en
Feature: Iteration UX
  As a beatmaker
  I want viewport control, fast core sliders and a first-run tour
  To iterate covers without freezes on any machine

  Scenario: Viewport intervals per mode
    Given a live viewport by default
    When I resolve intervals for full and still
    Then full is instant and still never auto-refreshes

  Scenario: Heavy presets are detected for the background path
    Given a clean preset and a blur preset
    When I check heaviness
    Then only the blur preset is heavy

# language: en
Feature: Stackable FX pipeline
  As a beatmaker
  I want to reorder and bypass post-dither effects
  To stack a custom cover look without leaving TRAKKART

  Scenario: Reordering grain and vignette changes the output
    Given a 48x48 gradient image
    When I render grain-then-vignette and vignette-then-grain
    Then the two outputs differ

  Scenario: JPEG glitch is deterministic and bypassable
    Given a 48x48 gradient image
    When I apply JPEG glitch twice with amount 60
    Then both JPEG outputs are identical

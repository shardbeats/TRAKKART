# language: en
Feature: Clip import
  As a beatmaker
  I want a short clip as a dither input
  To post motion cut from footage, not from stills

  Scenario: Clip dither is deterministic per frame
    Given a 48x48 gradient image
    When I dither a 3-frame clip twice with the same preset
    Then both clip outputs match frame by frame

  Scenario: Clip trim picks the inclusive range
    Given a 48x48 gradient image
    When I trim a 5-frame clip from 1 to 3
    Then the trim holds 3 frames starting with the second

  Scenario: Clip in-point skips the head of the clip
    Given a 48x48 gradient image
    When I import a 10-frame GIF from 0.3s
    Then the import starts at the fourth frame and flags truncation

  Scenario: Empty envelopes render byte-identical
    Given a 48x48 gradient image
    When I render a still animation with empty envelopes
    Then the envelope output matches the flat output

  Scenario: A grain ramp moves pixels deterministically
    Given a 48x48 gradient image
    When I render a still animation with a grain ramp
    Then the ramp output differs and re-renders identically

  Scenario: Full-length plan covers the whole clip
    Given a 48x48 gradient image
    When I plan a full-length export of a 10-frame GIF
    Then the plan holds 10 frames uncapped from the in-point

  Scenario: Noisy clip estimates heavier than quiet
    Given a 48x48 gradient image
    When I estimate clip MP4 weight quiet versus noisy
    Then the noisy estimate is several times the quiet one

  Scenario: Recipe key honors envelopes
    Given a 48x48 gradient image
    When I sign a recipe with and without a grain ramp
    Then the envelope key differs

  Scenario: Short track against a long clip warns
    Given a 48x48 gradient image
    When I compare a 3s track against a 10s clip
    Then the note mentions trailing silence

  Scenario: Filmstrip covers a long clip
    Given a 48x48 gradient image
    When I lay out a 120-frame strip
    Then it holds 10 stops from first to last

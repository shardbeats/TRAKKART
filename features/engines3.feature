# language: en
Feature: Engines III and print
  As a beatmaker
  I want more dither engines, CMYK, ASCII and black-vector
  To cover screens and merch from one offline app

  Scenario: New ordered engines render B&W
    Given a 48x48 gradient image
    When I render bayer32, lines and grid in B&W
    Then every result keeps the 48x48 size and is B&W

  Scenario: CMYK halftone is deterministic and animated by phase
    Given a 48x48 gradient image
    When I render CMYK twice with phase 0 and once with phase 4
    Then the phase 0 outputs match and the phase 4 differs

  Scenario: Motif custom config differs from default
    Given a 48x48 gradient image
    When I render motif default and motif ring custom
    Then the two motif outputs differ

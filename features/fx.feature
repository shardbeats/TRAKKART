# language: en
Feature: Finishing effects
  As a beatmaker
  I want scanlines and a brand color
  For a CRT look with my own stamp

  Scenario: Scanlines darken alternate rows
    Given a test image with marked rows
    When I apply scanlines every 4 rows
    Then row 3 ends up darkened and row 0 intact

  Scenario: Replace-color swaps whites
    Given a fully white test image
    When I replace white with #112233
    Then the whole image ends up in that color

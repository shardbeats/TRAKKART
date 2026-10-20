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

  Scenario: Duotone maps darks and lights
    Given a test image with gradient
    When I apply duotone black to white
    Then darks stay dark and lights stay light

  Scenario: Halftone dots reshape the image
    Given a 128x128 test image
    When I apply halftone dots of size 6
    Then the image keeps its size and changes

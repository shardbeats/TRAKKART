# language: en
Feature: Ordered Bayer dither
  As a beatmaker
  I want to apply Bayer dither to my cover
  To get a retro look, offline

  Scenario: B&W Bayer only outputs black and white
    Given a 64x64 test gradient
    When I apply 4x4 B&W Bayer with threshold 128
    Then the image only contains the values 0 and 255
    And the image keeps the 64x64 size

  Scenario: Palette Bayer only uses palette colors
    Given a 64x64 test gradient
    When I apply 4x4 Bayer with the SLIME palette
    Then every pixel belongs to the SLIME palette

  Scenario: Method dispatch keeps size
    Given a 64x64 test gradient
    When I apply each method bayer4, bayer8 and floyd in B&W
    Then every result keeps the 64x64 size

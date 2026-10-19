# language: en
Feature: Extra dither engines
  As a beatmaker
  I want more textures (Atkinson, blue-noise...)
  To vary the look of my covers

  Scenario: B&W Atkinson only outputs black and white
    Given a 64x64 test gradient
    When I apply B&W Atkinson
    Then the image only contains the values 0 and 255

  Scenario: Blue-noise is deterministic
    Given a 64x64 test gradient
    When I apply blue-noise twice
    Then both outputs are identical

  Scenario: B&W halftone only outputs black and white
    Given a 64x64 test gradient
    When I apply B&W halftone
    Then the image only contains the values 0 and 255

  Scenario: JJN with palette honors the palette
    Given a 64x64 test gradient
    When I apply JJN with the SLIME palette
    Then every pixel belongs to the SLIME palette

  Scenario: Numba and numpy agree
    Given a 64x64 test gradient
    When I diffuse Floyd with both backends
    Then both outputs are identical

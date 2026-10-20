# language: en
Feature: Palettes and export
  As a beatmaker
  I want built-in palettes and a store-ready export
  To publish without cloud tools

  Scenario: Palettes available and BW is the fast path
    Given the TRAKKART palette catalog
    Then BW exists and resolves to the palette-less fast path
    And SLIME holds 4 colors

  Scenario: Export generates main image, thumb and metadata
    Given a 128x128 solid test image
    When I export the image with base "t"
    Then image, thumb and metadata exist
    And thumb_1080p is 1920x1080
    And the main image honors the 3000 long side

  Scenario: Export smoke stays above 500B per PNG
    Given a 128x128 solid test image
    When I export the image with base "smoke"
    Then every PNG weighs more than 500 bytes

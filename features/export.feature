# language: en
Feature: Palettes and export bundle
  As a beatmaker
  I want built-in palettes and a store-ready bundle
  To publish without cloud tools

  Scenario: Palettes available and BW is the fast path
    Given the TRAKKART palette catalog
    Then BW exists and resolves to the palette-less fast path
    And SLIME holds 4 colors

  Scenario: Export bundle generates 3000, small and 1080p thumb
    Given a 128x128 solid test image
    When I export the bundle with base "t"
    Then cover, small and thumb_1080p exist
    And thumb_1080p is 1920x1080
    And cover is 3000x3000

  Scenario: Export smoke stays above 500B per PNG
    Given a 128x128 solid test image
    When I export the bundle with base "smoke"
    Then every PNG weighs more than 500 bytes

# language: en
Feature: Adjustments and metadata
  As a beatmaker
  I want to adjust brightness and get valid metadata
  To publish without opening another editor

  Scenario: High brightness changes the dither output
    Given a 64x64 test gradient
    When I apply 4x4 Bayer with brightness 1.5 and with brightness 1.0
    Then both outputs differ

  Scenario: Export includes valid metadata.json
    Given a 128x128 solid test image
    When I export the bundle with preset metadata
    Then metadata exists with TRAKKART app and params

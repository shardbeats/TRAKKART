# language: en
Feature: Canvas per ratio
  As a beatmaker
  I want covers in 1:1, 4:3, 9:16 and more
  For feed, stories and YouTube without another editor

  Scenario: 9:16 export honors dimensions
    Given a 128x128 solid test image
    When I export the image with 9:16 ratio
    Then the main image matches the expected size for 9:16 at 3000
    And thumb_1080p is 1920x1080

  Scenario: Out-of-range crop gets clamped
    Given a 64x64 test gradient
    When I crop to 9:16 with out-of-range focus
    Then the resulting canvas honors the 9:16 ratio

  Scenario: Custom canvas uses free WxH
    Given a 128x128 solid test image
    When I export the image with custom 1920x800 canvas
    Then the main image is exactly 1920x800

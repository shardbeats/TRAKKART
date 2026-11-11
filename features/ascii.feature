# language: en
Feature: ASCII art mode
  As a beatmaker
  I want a resolution-independent ASCII renderer
  To turn covers into text art with stable density

  Scenario: ASCII keeps size and is deterministic
    Given a 64x64 test gradient
    When I apply ASCII twice with 32 columns
    Then both outputs are identical
    And the image keeps the 64x64 size

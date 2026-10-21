# language: en
Feature: Cover flow and glitch
  As a beatmaker
  I want undoable ops and glitch effects
  To iterate fast without leaving the app

  Scenario: Chromatic aberration moves the red channel
    Given a test image with gradient
    When I apply chromatic aberration dx 4
    Then the R channel shifts and the G channel stays intact

  Scenario: Slice shift is deterministic
    Given a test image with gradient
    When I apply slice shift twice
    Then both outputs are identical

  Scenario: Pixel sort orders bright runs
    Given a test image with gradient
    When I apply pixel sort with threshold 128
    Then the image keeps its size and changes

  Scenario: Datamosh modes are deterministic and distinct
    Given a test image with gradient
    When I apply every mosh mode twice
    Then each mode is deterministic and modes differ

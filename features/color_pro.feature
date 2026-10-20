# language: en
Feature: Color Pro
  As a beatmaker
  I want source palettes, depth, midtones and highlights
  To nail cover color without leaving TRAKKART

  Scenario: Auto-extract palette is deterministic
    Given a test image with 2 flat colors
    When I extract 2 colors twice
    Then both extractions are identical

  Scenario: SOURCE mode renders at canvas size
    Given a test image with 2 flat colors
    When I render with SOURCE palette and depth 2
    Then the image keeps its canvas size

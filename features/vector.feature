# language: en
Feature: SVG vector
  As a beatmaker
  I want my cover as vector for logos and merch
  Without extra programs

  Scenario: Vector export generates valid SVG
    Given a test image with 2 flat colors
    When I generate the SVG with cell 8
    Then the SVG opens with <svg and closes with </svg>
    And it holds one rect per color run

  Scenario: Vector export groups runs one layer per ink
    Given a test image with 2 flat colors
    When I generate the layered SVG with cell 8
    Then it holds 2 ink layers and 32 rects

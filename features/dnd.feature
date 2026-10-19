# language: en
Feature: Drop classification
  As a beatmaker
  I want drops to be interpreted correctly
  Without processing anything without my say-so

  Scenario: Browser blob is neither folder nor file
    Given the text "blob:https://web.whatsapp.com/abc"
    When I classify the drop
    Then the action is "blob" and not batch

  Scenario: HTTP is classified as download
    Given the text "https://ejemplo.com/cover.png"
    When I classify the drop
    Then the action is "http" and not batch

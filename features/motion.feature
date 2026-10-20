# language: en
Feature: Motion from stills
  As a beatmaker
  I want retro-screen drift and MP4 export from my still cover
  To post motion without importing video anywhere

  Scenario: Signal Drift is deterministic and phase-animated
    Given a 48x48 gradient image
    When I apply snow drift twice with phase 0 and once with phase 3
    Then the phase 0 drifts match and the phase 3 differs

  Scenario: Paste-Up stays neutral when off
    Given a 48x48 gradient image
    When I render with paste-up off and paste-up paper at 0
    Then both outputs match the plain render

  Scenario: Missing video backend fails with install instructions
    Given no video backend installed
    When I try to write an MP4
    Then it raises VideoBackendMissing with pip instructions

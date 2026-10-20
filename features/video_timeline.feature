# language: en
Feature: Video timeline and Signal Drift
  As a beatmaker
  I want animated layers, retro-screen drift and clip import
  To turn still covers into motion without leaving TRAKKART

  Scenario: Signal Drift is deterministic and phase-animated
    Given a 48x48 gradient image
    When I apply snow drift twice with phase 0 and once with phase 3
    Then the phase 0 drifts match and the phase 3 differs

  Scenario: A timeline layer sweeps threshold across frames
    Given a 48x48 gradient image
    When I evaluate a threshold layer from 60 to 200 over 4 frames
    Then frame 0 uses 60 and frame 3 uses 200

  Scenario: Missing video backend fails with install instructions
    Given no video backend installed
    When I try to read a clip
    Then it raises VideoBackendMissing with pip instructions

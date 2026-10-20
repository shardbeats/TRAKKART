# language: en
Feature: Animated GIF
  As a beatmaker
  I want my cover animated for socials
  Without video or extra dependencies

  Scenario: GIF has N frames capped at 480px
    Given a 128x128 test image
    When I generate 4 frames in phase mode
    Then there are 4 frames and none exceeds 480px per side

  Scenario: Glitch mode animates even with static diffusion
    Given a 128x128 test image
    When I generate 4 frames in glitch mode
    Then the glitch frames differ from each other

  Scenario: Mix mode loops without a jump cut
    Given a 128x128 test image
    When I generate 4 frames in mix ping-pong mode
    Then the ping-pong loop has 6 frames and loops smoothly

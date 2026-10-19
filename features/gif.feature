# language: en
Feature: Animated GIF
  As a beatmaker
  I want my cover animated for socials
  Without video or extra dependencies

  Scenario: GIF has N frames capped at 480px
    Given a 128x128 test image
    When I generate 4 frames in phase mode
    Then there are 4 frames and none exceeds 480px per side

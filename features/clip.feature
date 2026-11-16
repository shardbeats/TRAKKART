# language: en
Feature: Clip import
  As a beatmaker
  I want a short clip as a dither input
  To post motion cut from footage, not from stills

  Scenario: Clip dither is deterministic per frame
    Given a 48x48 gradient image
    When I dither a 3-frame clip twice with the same preset
    Then both clip outputs match frame by frame

  Scenario: Clip trim picks the inclusive range
    Given a 48x48 gradient image
    When I trim a 5-frame clip from 1 to 3
    Then the trim holds 3 frames starting with the second

# language: en
Feature: Morph particle fields
  As a beatmaker
  I want directional dispersions, staggered pours and envelopes
  To animate covers beyond wind and random

  Scenario: Burst field is deterministic and moves
    Given a 48x48 gradient image
    When I disperse it twice in burst mode and once in wind mode
    Then the burst runs match and differ from the wind run

  Scenario: Stagger off is legacy-neutral
    Given a 48x48 gradient image
    When I disperse it with explicit wind off sine and with rank stagger
    Then the explicit legacy matches the default and the stagger differs

  Scenario: Blocks shows every form assembled
    Given two flat images
    When I morph them in blocks mode without loop
    Then the first frame is A assembled and the last is B assembled

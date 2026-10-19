# language: en
Feature: Export history
  As a beatmaker
  I want a log of what I export
  To know which preset I used on each cover

  Scenario: Export gets recorded in history
    Given an empty temporary history
    When I log an export with base "beat_hist" and preset "SLIME_FS"
    Then the history holds 1 record with that base

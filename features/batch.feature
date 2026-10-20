# language: en
Feature: Folder batch
  As a beatmaker
  I want to process a whole cover folder at once
  Instead of going image by image

  Scenario: Batch of 3 images generates bundles
    Given a temporary folder with 3 48x48 images
    When I run batch with bayer4 preset and SLIME palette
    Then the 3 files end up ok with 2 PNGs each

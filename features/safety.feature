# language: en
Feature: Safety limits
  As a beatmaker
  I want the app to never freeze or blow up
  Even when I load huge files

  Scenario: Giant image is rejected without decoding
    Given a 9000-pixel-wide image
    When I validate its size
    Then it fails with TooBigError

  Scenario: Huge vector is blocked before rendering
    Given a 2000x2000 image
    When I generate the vector with cell 4
    Then it fails with TooBigError without rendering

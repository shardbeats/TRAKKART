# language: en
Feature: Floyd-Steinberg error diffusion
  As a beatmaker
  I want to diffuse quantization error
  To get smooth gradients with few colors

  Scenario: B&W Floyd only outputs black and white
    Given a 64x64 test gradient
    When I apply B&W Floyd-Steinberg with threshold 128
    Then the image only contains the values 0 and 255

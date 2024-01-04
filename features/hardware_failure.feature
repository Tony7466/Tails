@product
Feature: Hardware failures
  As a Tails user
  when The USB stick has hardware failures
  I want to to see a message.

  Scenario: Tails shows a message if the disk has read failures.
    Given I have started Tails from DVD without network and logged in
    When Tails detect disk read failures
    Then I see a Disk Failure Message

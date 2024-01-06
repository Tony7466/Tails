@product
Feature: Hardware failures
  As a Tails user
  when The USB stick has hardware failures
  I want to to see a message.

  Scenario: After I log in I see an error message
    Given I have started Tails from DVD without network and logged in
    When Tails detect disk read failures
    Then I see a Disk Failure Message

  Scenario: Before I log in I see an error message
    Given the computer boots Tails
    When Tails detect disk read failures
    Then Greeter does not start and I see a Plymouth Disk Failure Message instead

@product @doc @not_release_blocker
Feature: Tails documentation

  Scenario: The Tails documentation launcher on the desktop works when offline
    Given I have started Tails from DVD without network and logged in
    When I open the Tails documentation launcher on the desktop
    Then "Tails - Documentation" has loaded in the Tor Browser

  Scenario: The Tails documentation launcher on the desktop works when online
    Given I have started Tails from DVD and logged in and the network is connected
    When I open the Tails documentation launcher on the desktop
    Then "Tails - Documentation" has loaded in the Tor Browser

  Scenario: The Report an Error launcher opens the support documentation
    Given I have started Tails from DVD without network and logged in
    When I open the Report an Error launcher on the desktop
    Then the support documentation page opens in Tor Browser

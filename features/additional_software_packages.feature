@product @check_tor_leaks @slow

Feature: Additional software
  As a Tails user
  I may want to install softwares not shipped in Tails
  And have them installed automatically when I enable persistence in the Greeter

  #18852
  @not_release_blocker @fragile
  Scenario: I am warned I can not use Additional Software when I start Tails from a DVD and install a package
    Given I have started Tails from DVD and logged in with an administration password and the network is connected
    And I update APT using apt
    When I install "popularity-contest" using apt
    Then I am notified I can not use Additional Software for "popularity-contest"
    And I can open the Additional Software documentation from the notification

  # Here we install the popularity-contest package to test if debconf does not prevent
  # Additional Software from automatically installing packages.
  # This scenario also sets up the "__internal" drive that the following
  # scenarios will reuse.
  # Note: the "__internal" drive will keep its state across scenarios
  # and features until one of its snapshots is restored.
  Scenario: I set up Additional Software when installing a package without persistent partition and the package is installed next time I start Tails
    Given I start Tails from a freshly installed USB drive with an administration password and the network is plugged and I login
    And I update APT using apt
    And I install "popularity-contest" using apt
    Then I am proposed to add the "popularity-contest" package to my Additional Software
    When I create a persistent storage and activate the Additional Software feature
    Then Additional Software is correctly configured for package "popularity-contest"
    When I shutdown Tails and wait for the computer to power off
    And I start Tails from USB drive "__internal" with network unplugged and I login with persistence enabled
    Then Additional Software is correctly configured for package "popularity-contest"
    And the package "popularity-contest" is installed after Additional Software has been started

  Scenario: The Additional Software dpkg hook notices when persistence is locked down while installing a package
    Given I have started Tails without network from a USB drive with a persistent partition and stopped at Tails Greeter's login screen
    When I set an administration password
    And I log in to a new session
    And the network is plugged
    And Tor is ready
    And all notifications have disappeared
    And I update APT using apt
    When I install "makepp" using apt
    Then the Additional Software dpkg hook has been run for package "makepp" and notices the persistence is locked
    And the package "makepp" is installed

  Scenario: My Additional Software list is configurable through a GUI or through notifications when I install or remove packages with APT or Synaptic
    Given I have started Tails from a USB drive and logged in with an administration password and Persistent Storage enabled and the network is connected and I updated APT
    When I install "popularity-contest" using apt
    And I accept adding "popularity-contest" to Additional Software
    Then Additional Software is correctly configured for package "popularity-contest"
    When I uninstall "popularity-contest" using apt
    And I accept removing "popularity-contest" from Additional Software
    Then "popularity-contest" is not in the list of Additional Software
    When I start Synaptic
    And I update APT using Synaptic
    And I install "cowsay" using Synaptic
    And I accept adding "cowsay" to Additional Software
    Then Additional Software is correctly configured for package "cowsay"
    When I uninstall "cowsay" using apt
    And I refuse removing "cowsay" from Additional Software
    Then Additional Software is correctly configured for package "cowsay"
    When I start "Additional Software" via GNOME Activities Overview
    And I remove "cowsay" from the list of Additional Software using Additional Software GUI
    Then "cowsay" is not in the list of Additional Software
    When I install "cowsay" using apt
    And I refuse adding "cowsay" to Additional Software
    Then "cowsay" is not in the list of Additional Software

  # See https://tails.boum.org/blueprint/additional_software_packages/offline_mode/#incomplete-online-upgrade for high level logic
  #19233
  @not_release_blocker @fragile
  Scenario: Recovering in offline mode after Additional Software previously failed to upgrade and then succeed to upgrade when online
    Given I have started Tails from a USB drive and logged in with an administration password and Persistent Storage enabled and the network is connected and I updated APT
    When I configure APT to prefer an old version of cowsay
    And I install an old version "3.03+dfsg2-1" of the cowsay package using apt
    And I accept adding "cowsay" to Additional Software
    Then Additional Software is correctly configured for package "cowsay"
    When I shutdown Tails and wait for the computer to power off
    And I start Tails from USB drive "__internal" with network unplugged
    And I enable persistence
    # We need to add back this custom APT source for the Additional Software
    # install step, as it was not saved in persistence
    And I configure APT to prefer an old version of cowsay
    And I log in to a new session
    Then the installed version of package "cowsay" is "3.03+dfsg2-1" after Additional Software has been started
    When I revert the APT tweaks that made it prefer an old version of cowsay
    # We remove the newest package after it has been downloaded and before
    # it is installed, so that the upgrade process fails
    And I prepare the Additional Software upgrade process to fail
    And the network is plugged
    And Tor is ready
    # Note: the next step races against the appearance of the "The
    # upgrade of your additional software failed" notification.
    # It should win most of the time, which is good, but there's no
    # guarantee it does. If it loses, then it'll remove the notification
    # we'll be trying to interact with below ("I can open…")
    And all notifications have disappeared
    And available upgrades have been checked
    And I see the "The upgrade of your additional software failed" notification after at most 300 seconds
    And I can open the Additional Software configuration window from the notification
    And I shutdown Tails and wait for the computer to power off
    And I start Tails from USB drive "__internal" with network unplugged
    And I enable persistence
    # We need to add back this custom APT source for the Additional Software
    # install step, as it was not saved in persistence
    And I configure APT to prefer an old version of cowsay
    And I log in to a new session
    And the installed version of package "cowsay" is "3.03+dfsg2-1" after Additional Software has been started
    And I revert the APT tweaks that made it prefer an old version of cowsay
    And the network is plugged
    And Tor is ready
    Then the Additional Software upgrade service has started
    And the installed version of package "cowsay" is newer than "3.03+dfsg2-1"

  @not_release_blocker_inherited @fragile
  Scenario: I am notified when Additional Software fails to install a package
    Given I have started Tails from a USB drive and logged in with an administration password and Persistent Storage enabled and the network is connected and I updated APT
    When I install "cowsay" using apt
    And I accept adding "cowsay" to Additional Software
    Then Additional Software is correctly configured for package "cowsay"
    When I remove the "cowsay" deb files from the APT cache
    And I shutdown Tails and wait for the computer to power off
    And I start Tails from USB drive "__internal" with network unplugged and I login with persistence enabled
    # Prevent the "Warning: virtual machine detected!" notification from racing
    # with the one we'll be interacting with below.
    And I disable the tails-virt-notify-user.service user unit
    And I log in to a new session
    Then I see the "The installation of your additional software failed" notification after at most 300 seconds
    And I can open the Additional Software log file from the notification
    And the package "cowsay" is not installed

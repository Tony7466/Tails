@product
Feature: Tails persistence
  As a Tails user
  I want to use a Persistent Storage

  Scenario: Tails Persistent Storage behave tests
    Given I have started Tails from a USB drive and logged in with an administration password and Persistent Storage enabled and the network is connected and I updated APT
    And I install "python3-behave" using apt
    Then the Tails Persistent Storage behave tests pass

  Scenario: Booting Tails from a USB drive with a disabled persistent partition
    Given I have started Tails without network from a USB drive with a persistent partition and stopped at Tails Greeter's login screen
    When I log in to a new session without activating the Persistent Storage
    Then Tails is running from USB drive "__internal"
    And persistence is disabled
    But a Tails persistence partition exists on USB drive "__internal"

  Scenario: Creating a Persistent Storage
    Given I have started Tails without network from a USB drive without a persistent partition and logged in
    Then Tails is running from USB drive "__internal"
    When I create a file in the Persistent directory
    And I create a persistent partition with the default settings
    Then the file I created was copied to the Persistent Storage
    When I shutdown Tails and wait for the computer to power off
    And I start Tails from USB drive "__internal" with network unplugged and I login with persistence enabled
    Then persistence for "Persistent" is active
    And the file I created in the Persistent directory exists

  Scenario: Booting Tails from a USB drive with an enabled persistent partition and reconfiguring it
    Given I have started Tails without network from a USB drive with a persistent partition enabled and logged in
    Then Tails is running from USB drive "__internal"
    And all tps features are active
    And all persistent directories have safe access rights
    When I disable the first tps feature
    Then all tps features but the first one are active
    And I shutdown Tails and wait for the computer to power off
    And I start Tails from USB drive "__internal" with network unplugged and I login with persistence enabled
    Then all tps features but the first one are active

  Scenario: Activating and deactivating Persistent Storage features
    Given I have started Tails without network from a USB drive with a persistent partition enabled and logged in
    Then persistence for "Persistent" is active
    And I create a file in the Persistent directory
    Then the file I created was copied to the Persistent Storage
    When I disable the first tps feature
    Then persistence for "Persistent" is not active
    And the Persistent directory does not exist
    When I enable the first tps feature
    Then persistence for "Persistent" is active
    And the file I created in the Persistent directory exists

  Scenario: Deleting data of a Persistent Storage feature
    Given I have started Tails without network from a USB drive with a persistent partition enabled and logged in
    Then persistence for "Persistent" is active
    When I create a file in the Persistent directory
    And I disable the first tps feature
    And I delete the data of the Persistent Folder feature
    Then the file I created does not exist on the Persistent Storage

  Scenario: Writing files to a read/write-enabled persistent partition
    Given I have started Tails without network from a USB drive with a persistent partition enabled and logged in
    And the network is plugged
    And Tor is ready
    And I take note of which tps features are available
    When I write some files expected to persist
    And I shutdown Tails and wait for the computer to power off
    # XXX: The next step succeeds (and the --debug output confirms that it's actually looking for the files) but will fail in a subsequent scenario restoring the same snapshot. This exactly what we want, but why does it work? What is guestfs's behaviour when qcow2 internal snapshots are involved?
    Then only the expected files are present on the persistence partition on USB drive "__internal"

  Scenario: Creating and using a persistent NetworkManager connection
    Given I have started Tails without network from a USB drive with a persistent partition enabled and logged in
    And the network is plugged
    And Tor is ready
    And I add a wired DHCP NetworkManager connection called "persistent-con-current"
    And I shutdown Tails and wait for the computer to power off
    Given I start Tails from USB drive "__internal" with network unplugged and I login with persistence enabled
    And I capture all network traffic
    And the network is plugged
    And Tor is ready
    And I switch to the "persistent-con-current" NetworkManager connection
    And the 1st network device has a spoofed MAC address configured
    And no network device leaked the real MAC address

  Scenario: Creating persistence from the Welcome Screen
    Given I have started Tails without network from a USB drive without a persistent partition and stopped at Tails Greeter's login screen
    And I enable persistence creation in Tails Greeter
    And I log in to a new session expecting no warning about the Persistent Storage not being activated
    Then I create a persistent partition with the default settings using the wizard that was already open

  Scenario: Persistent Greeter options
    Given I have started Tails without network from a USB drive with a persistent partition and stopped at Tails Greeter's login screen
    When I enable persistence
    Then no persistent Greeter options were restored
    When I set all Greeter options to non-default values
    And I log in to a new session in German (de) after having activated the Persistent Storage
    Then all Greeter options are set to non-default values
    When I cold reboot the computer
    And the computer reboots Tails
    Given I enable persistence
    Then persistent Greeter options were restored
    When I log in to a new session after having activated the Persistent Storage
    Then all Greeter options are set to non-default values

  Scenario: Changing the Persistent Storage passphrase
    Given I have started Tails without network from a USB drive with a persistent partition enabled and logged in
    # Note that if anything fails after the passphrase was changed and
    # before it's changed back below, subsequent scenarios might fail
    # because the Persistent Storage doesn't have the expected passphrase.
    When I change the passphrase of the Persistent Storage
    And I shutdown Tails and wait for the computer to power off
    Then I start Tails from USB drive "__internal" with network unplugged and I login with the changed persistence passphrase
    And I change the passphrase of the Persistent Storage back to the original

  Scenario: Deleting a Tails persistent partition
    Given I have started Tails without network from a USB drive with a persistent partition and stopped at Tails Greeter's login screen
    And I log in to a new session without activating the Persistent Storage
    And persistence is disabled
    But a Tails persistence partition exists on USB drive "__internal"
    And all notifications have disappeared
    When I delete the persistent partition
    Then there is no persistence partition on USB drive "__internal"

  Scenario: Dotfiles persistence
    Given I have started Tails without network from a USB drive with a persistent partition enabled and logged in
    When I write some dotfile expected to persist
    And I shutdown Tails and wait for the computer to power off
    And I start Tails from USB drive "__internal" with network unplugged and I login with persistence enabled
    Then the expected persistent dotfile is present in the filesystem

  Scenario: Feature activation fails
    Given I have started Tails without network from a USB drive with a persistent partition and stopped at Tails Greeter's login screen
    And I create a symlink "/home/amnesia/Persistent" to "/etc"
    When I enable persistence
    Then the Welcome Screen tells me that the Persistent Folder feature couldn't be activated
    When I log in to a new session after having activated the Persistent Storage
    Then the Persistent Storage settings tell me that the Persistent Folder feature couldn't be activated
    And all tps features are enabled
    And all tps features but the first one are active

When /^Tails detect disk read failures$/ do
  squashfs_failed = '/var/lib/live/tails.squashfs_failed'
  $vm.execute('systemct --now disable tails-detect-squashfs-errors')
  $vm.execute_successfully("touch #{squashfs_failed}")
  try_for(60) { $vm.file_exist?(squashfs_failed) }
end

Then /^I see a Disk Failure Message$/ do
  @screen.wait('GnomeDiskFailureMessage.png', 10)
end

Then /^Greeter does not start and I see a Plymouth Disk Failure Message instead$/ do
  @screen.wait('PlymouthDiskFailureMessage.png', 10)
end

When /^Tails detect disk read failures$/ do
  squashfs_failed = "/var/lib/live/tails.squashfs_failed"
  $m.execute("touch #{squashfs_failed}")
  try_for(60) { $vm.file_exist?(squashfs_failed) }
end

Then /^I see a Disk Failure Message$/ do
  @screen.wait('GnomeDiskFailureMessage.png',10)
end

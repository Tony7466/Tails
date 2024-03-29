require 'English'
require 'expect'
require 'pty'
require 'tempfile'

$veracrypt_passphrase = 'test'
$veracrypt_hidden_passphrase = 'fdsa'
$veracrypt_volume_name = 'veracrypt'
$veracrypt_pim = '1'
$veracrypt_basic_container_with_pim = "#{MISC_FILES_DIR}/container_with_pim.hc"

def veracrypt_volume_size_in_nautilus(**options)
  if options[:isHidden]
    '52 MB'
  else
    options[:needsPim] ? '147 KB' : '105 MB'
  end
end

def veracrypt_volume_size_in_gnome_disks(**options)
  options[:needsPim] ? '410 KB' : '105 MB'
end

def create_veracrypt_keyfile
  keyfile = Tempfile.create('veracrypt-keyfile', $config['TMPDIR'])
  keyfile << 'asdf'
  keyfile.close
  keyfile.path
end

def reply_prompt(r_f, w_f, prompt_re, answer)
  r_f.expect(prompt_re) do
    debug_log "got prompt, typing #{answer}"
    sleep 1 # tcplay takes some time before it's ready to read our input
    w_f.puts answer.to_s
  end
end

def prepare_veracrypt_volume(type, with_keyfile)
  @veracrypt_is_hidden = (type == 'hidden')
  @veracrypt_needs_keyfile = with_keyfile
  step 'I temporarily create a 100 MiB raw disk named ' \
       "\"#{$veracrypt_volume_name}\""
  disk_path = $vm.storage.disk_path($veracrypt_volume_name)
  keyfile = create_veracrypt_keyfile
  fatal_system "losetup -f '#{disk_path}'"
  loop_dev = `losetup -j '#{disk_path}'`.split(':').first
  create_veracrypt_volume(loop_dev, keyfile)
  map_veracrypt_volume(loop_dev, keyfile)
  populate_veracrypt_volume('veracrypt')
  fatal_system 'tcplay --unmap=veracrypt'
  fatal_system "losetup -d '#{loop_dev}'"
  File.delete(keyfile)
end

def create_veracrypt_volume(block_device, keyfile)
  tcplay_create_cmd = "tcplay --create --device='#{block_device}' " \
                      '--weak-keys --insecure-erase'
  tcplay_create_cmd += ' --hidden' if @veracrypt_is_hidden
  tcplay_create_cmd += " --keyfile='#{keyfile}'" if @veracrypt_needs_keyfile
  debug_log "tcplay create command: #{tcplay_create_cmd}"
  PTY.spawn(tcplay_create_cmd) do |r_f, w_f, pid|
    begin
      w_f.sync = true
      reply_prompt(r_f, w_f, /^Passphrase:\s/, $veracrypt_passphrase)
      reply_prompt(r_f, w_f, /^Repeat passphrase:\s/, $veracrypt_passphrase)
      if @veracrypt_is_hidden
        reply_prompt(r_f, w_f, /^Passphrase for hidden volume:\s/,
                     $veracrypt_hidden_passphrase)
        reply_prompt(r_f, w_f, /^Repeat passphrase:\s/,
                     $veracrypt_hidden_passphrase)
        reply_prompt(r_f, w_f, /^Size of hidden volume.*:\s/, '50M')
      end
      reply_prompt(r_f, w_f, /^\s*Are you sure you want to proceed/, 'y')
      r_f.expect(/^All done!/)
    rescue Errno::EIO
      # Handled by checking $CHILD_STATUS below
    ensure
      Process.wait pid
    end
    $CHILD_STATUS.exitstatus.zero? || raise(
      "#{tcplay_create_cmd} exited with #{$CHILD_STATUS.exitstatus}"
    )
  end
end

def map_veracrypt_volume(block_device, keyfile)
  tcplay_map_cmd = "tcplay --map=veracrypt --device='#{block_device}'"
  tcplay_map_cmd += " --keyfile='#{keyfile}'" if @veracrypt_needs_keyfile
  debug_log "tcplay map command: #{tcplay_map_cmd}"
  PTY.spawn(tcplay_map_cmd) do |r_f, w_f, pid|
    begin
      w_f.sync = true
      reply_prompt(
        r_f, w_f, /^Passphrase:\s/,
        if @veracrypt_is_hidden
          $veracrypt_hidden_passphrase
        else
          $veracrypt_passphrase
        end
      )
      r_f.expect(/^All ok!/)
    rescue Errno::EIO
      # Handled by checking $CHILD_STATUS below
    ensure
      Process.wait pid
    end
    $CHILD_STATUS.exitstatus.zero? || raise(
      "#{tcplay_map_cmd} exited with #{$CHILD_STATUS.exitstatus}"
    )
  end
end

def populate_veracrypt_volume(unlocked_veracrypt_mapping)
  unlocked_block_device = "/dev/mapper/#{unlocked_veracrypt_mapping}"
  fatal_system "mkfs.vfat '#{unlocked_block_device}' >/dev/null"
  Dir.mktmpdir('veracrypt-mountpoint', $config['TMPDIR']) do |mountpoint|
    fatal_system "mount -t vfat '#{unlocked_block_device}' '#{mountpoint}'"
    # must match SecretFileOnVeraCryptVolume.png when displayed in GNOME Files
    FileUtils.cp('/usr/share/common-licenses/GPL-3', "#{mountpoint}/GPL-3")
    fatal_system "umount '#{mountpoint}'"
  end
end

When /^I plug a USB drive containing a (.+) VeraCrypt volume( with a keyfile)?$/ do |type, with_keyfile|
  prepare_veracrypt_volume(type, with_keyfile)
  step "I plug USB drive \"#{$veracrypt_volume_name}\""
end

When /^I plug and mount a USB drive containing a (.+) VeraCrypt file container( with a keyfile| with a PIM)?$/ do |type, with_options|
  case with_options
  when ' with a PIM'
    assert_equal('basic', type,
                 'Only basic containers are supported with PIM.')
    @veracrypt_needs_pim = true
    # Instead of creating a container, we use the one we have in Git.
    @veracrypt_shared_dir_in_guest = share_host_files(
      $veracrypt_basic_container_with_pim
    )
    src = "#{@veracrypt_shared_dir_in_guest}/" \
          "#{File.basename($veracrypt_basic_container_with_pim)}"
    dst = "#{@veracrypt_shared_dir_in_guest}/#{$veracrypt_volume_name}"
    $vm.execute_successfully("mv '#{src}' '#{dst}'")
  else
    @veracrypt_needs_pim = false
    prepare_veracrypt_volume(type, with_options)
    @veracrypt_shared_dir_in_guest = share_host_files(
      $vm.storage.disk_path($veracrypt_volume_name)
    )
  end
  $vm.execute_successfully(
    "chown #{LIVE_USER}:#{LIVE_USER} " \
    "'#{@veracrypt_shared_dir_in_guest}/#{$veracrypt_volume_name}'"
  )
end

When /^I unlock and mount this VeraCrypt (volume|file container) with Unlock VeraCrypt Volumes$/ do |support|
  step 'I start "Unlock VeraCrypt Volumes" via GNOME Activities Overview'
  case support
  when 'volume'
    @screen.wait('Gtk3UnlockButton.png', 10).click
  when 'file container'
    @screen.wait('UnlockVeraCryptVolumesAddButton.png', 10).click
    @screen.wait('Gtk3FileChooserDocumentsButton.png', 10)
    @screen.paste("#{@veracrypt_shared_dir_in_guest}/#{$veracrypt_volume_name}",
                  app: :gtk_file_chooser)
    sleep 2 # avoid ENTER being eaten by the auto-completion system
    @screen.press('Return')
  end
  @screen.wait('VeraCryptUnlockDialog.png', 10)
  @screen.paste(
    @veracrypt_is_hidden ? $veracrypt_hidden_passphrase : $veracrypt_passphrase,
    app: :gtk_file_chooser
  )
  if @veracrypt_needs_pim
    # Go back to the PIM entry text field
    @screen.press('shift', 'Tab')
    sleep 1 # Otherwise typing the PIM goes in the void
    @screen.type($veracrypt_pim)
  end
  if @veracrypt_is_hidden
    @screen.click('VeraCryptUnlockDialogHiddenVolumeLabel.png')
  end
  @screen.press('Return')
  @screen.wait_vanish('VeraCryptUnlockDialog.png', 10)
  try_for(30) do
    !$vm.file_glob('/media/amnesia/*/GPL-3').empty?
  end
end

When /^I unlock and mount this VeraCrypt (volume|file container) with GNOME Disks$/ do |support|
  step 'I start "Disks" via GNOME Activities Overview'
  disks = gnome_disks_app
  size = veracrypt_volume_size_in_gnome_disks(
    isHidden: @veracrypt_is_hidden,
    needsPim: @veracrypt_needs_pim
  )
  case support
  when 'volume'
    disks.children(roleName: 'table cell')
         .find { |row| /^#{size} Drive/.match(row.name) }
         .grabFocus
  when 'file container'
    @screen.wait('GnomeDisksApplicationsMenuButton.png', 10).click
    # Clicking this button using Dogtail works, but afterwards the
    # GNOME Disks GUI becomes inaccessible.
    disks.child('Attach Disk Image… (.iso, .img)', roleName: 'push button').grabFocus
    @screen.press('Return')
    # Otherwise Disks is sometimes minimized, for some reason I don't understand
    sleep 2
    attach_dialog = disks.child('Select Disk Image to Attach',
                                roleName: 'file chooser')
    attach_dialog.child('Set up read-only loop device',
                        roleName: 'check box').click
    filter = attach_dialog.child('Disk Images (*.img, *.iso)',
                                 roleName: 'combo box')
    filter.press
    try_for(5) do
      filter.child('All Files', roleName: 'menu item').click
      true
    rescue Dogtail::Failure
      # we probably clicked too early, which triggered an "Attempting
      # to generate a mouse event at negative coordinates" Dogtail error
      false
    end
    @screen.paste("#{@veracrypt_shared_dir_in_guest}/#{$veracrypt_volume_name}",
                  app: :gtk_file_chooser)
    sleep 2 # avoid ENTER being eaten by the auto-completion system
    @screen.press('Return')
    try_for(15) do
      disks.children(roleName: 'table cell')
           .find { |row| /^#{size} Loop Device/.match(row.name) }
           .grabFocus
      true
    rescue NoMethodError
      false
    end
  end
  disks.child('', roleName:    'panel',
                  description: 'Unlock selected encrypted partition')
       .child('Unlock', roleName: 'push button').click
  unlock_dialog = disks.dialog('Set options to unlock')
  unlock_dialog.child('', roleName: 'password text').grabFocus
  @screen.paste(
    @veracrypt_is_hidden ? $veracrypt_hidden_passphrase : $veracrypt_passphrase,
    app: :gtk_file_chooser
  )
  if @veracrypt_needs_pim
    unlock_dialog.child('PIM', roleName: 'label').labelee.grabFocus
    @screen.paste(
      $veracrypt_pim,
      app: :gtk_file_chooser
    )
  end
  if @veracrypt_needs_keyfile
    # XXX:Bullseye: port to Dogtail, as #15952 was fixed in GNOME Disks 3.35.2
    @screen.wait('GnomeDisksUnlockDialogKeyfileComboBox.png', 5)
    @screen.click('GnomeDisksUnlockDialogKeyfileComboBox.png')
    @screen.wait('Gtk3FileChooserDocumentsButton.png', 10)
    $vm.file_overwrite('/tmp/keyfile', 'asdf')
    @screen.paste('/tmp/keyfile',
                  app: :gtk_file_chooser)
    @screen.press('Return')
    @screen.wait_vanish('Gtk3FileChooserDocumentsButton.png', 10)
  end
  if @veracrypt_is_hidden
    @screen.wait('GnomeDisksUnlockDialogHiddenVolumeLabel.png', 10).click
  end
  # Clicking is robust neither with Dogtail (no visible effect) nor
  # with image matching (that sometimes clicks just a little bit
  # outside of the button)
  @screen.wait('Gtk3UnlockButton.png', 10)
  @screen.press('alt', 'u') # "Unlock" button
  try_for(30, msg: 'Failed to mount the unlocked volume') do
    disks.child("#{size} VeraCrypt/TrueCrypt",
                roleName: 'panel')
         .grabFocus
    # Move the focus down to the "Filesystem\n107 MB FAT" item (that Dogtail
    # is not able to find) using the 'Down' arrow, in order to display
    # the "Mount selected partition" button.
    sleep 0.5 # otherwise the following key press is sometimes lost
    @screen.press('down')
    disks.child('', roleName:    'panel',
                    description: 'Mount selected partition')
         .child('Mount', roleName: 'push button')
         .click
    true
  rescue Dogtail::Failure
    # we probably did something too early, which triggered a Dogtail error
    # such as "Attempting to generate a mouse event at negative coordinates"
    false
  end
  try_for(10, msg: '/media/amnesia/*/GPL-3 does not exist') do
    !$vm.file_glob('/media/amnesia/*/GPL-3').empty?
  end
end

When /^I open this VeraCrypt volume in GNOME Files$/ do
  $vm.spawn('nautilus /media/amnesia/*', user: LIVE_USER)
  volume_size_in_nautilus = veracrypt_volume_size_in_nautilus(
    isHidden: @veracrypt_is_hidden,
    needsPim: @veracrypt_needs_pim
  )
  Dogtail::Application.new('org.gnome.Nautilus').window(
    "#{volume_size_in_nautilus} Volume"
  )
end

When /^I lock the currently opened VeraCrypt (volume|file container)$/ do |support|
  $vm.execute_successfully(
    'udisksctl unmount --block-device /dev/mapper/tcrypt-*',
    user: LIVE_USER
  )
  device = support == 'volume' ? '/dev/sda' : '/dev/loop1'
  $vm.execute_successfully(
    "udisksctl lock --block-device #{device}",
    user: LIVE_USER
  )
end

Then /^the VeraCrypt (?:volume|file container) has been unmounted and locked$/ do
  assert_empty($vm.file_glob('/media/amnesia/*/GPL-3'))
  assert_empty($vm.file_glob('/dev/mapper/tcrypt-*'))
end

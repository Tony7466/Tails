def whisperback
  Dogtail::Application.new('whisperback')
end

Then(/^Whisperback has debugging info$/) do
  matching = whisperback.children(roleName: 'text', showingOnly: false).select do |x|
    x&.text&.slice(1, 50)&.include?('=== content of /proc/cmdline ===')
  end
  assert(!matching.empty?,
         'Could not find debugging info in whisperback window')
end
